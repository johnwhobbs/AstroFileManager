"""
Update Dialog for AstroFileManager.

Provides a user interface for checking, downloading, and applying updates.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QGroupBox, QRadioButton, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.update_manager import UpdateManager
from core.config_manager import ConfigManager


class UpdateCheckWorker(QThread):
    """
    Background worker thread for checking updates.

    Prevents UI freezing during network operations.
    """

    # Signals for communication with main thread
    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(dict)  # Update information dictionary

    def __init__(self, branch: str):
        """
        Initialize the update check worker.

        Args:
            branch: The branch to check (main or development)
        """
        super().__init__()
        self.branch = branch

    def run(self):
        """Execute the update check in background thread."""
        update_manager = UpdateManager(preferred_branch=self.branch)
        result = update_manager.check_for_updates(progress_callback=self.progress.emit)
        self.finished.emit(result)


class UpdateDownloadWorker(QThread):
    """
    Background worker thread for downloading updates.

    Handles download and application of updates without blocking UI.
    """

    # Signals
    progress = pyqtSignal(str)  # Progress message
    percent = pyqtSignal(int)   # Download percentage (0-100)
    finished = pyqtSignal(bool)  # Success/failure

    def __init__(self, branch: str):
        """
        Initialize the update download worker.

        Args:
            branch: The branch to download from (main or development)
        """
        super().__init__()
        self.branch = branch

    def run(self):
        """Execute the download and update in background thread."""
        update_manager = UpdateManager(preferred_branch=self.branch)

        # Download the update
        zip_path = update_manager.download_update(
            progress_callback=self.progress.emit,
            percent_callback=self.percent.emit
        )

        if zip_path is None:
            self.finished.emit(False)
            return

        # Apply the update
        success = update_manager.apply_update(
            zip_path,
            progress_callback=self.progress.emit
        )

        self.finished.emit(success)


class UpdateDialog(QDialog):
    """
    Dialog for managing application updates.

    Allows users to check for updates, select branch, download, and apply updates.
    """

    def __init__(self, parent=None):
        """
        Initialize the update dialog.

        Args:
            parent: Parent widget (usually the main window)
        """
        super().__init__(parent)
        self.settings = ConfigManager('AstroFileManager', 'AstroFileManager')
        self.update_info = None
        self.check_worker = None
        self.download_worker = None

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle('Check for Updates')
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout()

        # Branch selection group
        branch_group = QGroupBox("Update Source")
        branch_layout = QVBoxLayout()

        self.main_radio = QRadioButton("Main Branch (Stable)")
        self.main_radio.setToolTip("Production-ready stable releases")
        self.development_radio = QRadioButton("Development Branch (Latest features)")
        self.development_radio.setToolTip("Latest features, may be less stable")

        self.main_radio.setChecked(True)  # Default to main

        branch_layout.addWidget(self.main_radio)
        branch_layout.addWidget(self.development_radio)
        branch_group.setLayout(branch_layout)
        layout.addWidget(branch_group)

        # Current version info
        from constants import __VERSION__
        version_label = QLabel(f"Current Version: {__VERSION__}")
        version_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(version_label)

        # Status text area
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(200)
        layout.addWidget(self.status_text)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        button_layout = QHBoxLayout()

        self.check_button = QPushButton('Check for Updates')
        self.check_button.clicked.connect(self.check_for_updates)

        self.download_button = QPushButton('Download and Install Update')
        self.download_button.clicked.connect(self.download_and_install)
        self.download_button.setEnabled(False)

        self.restart_button = QPushButton('Restart Application')
        self.restart_button.clicked.connect(self.restart_application)
        self.restart_button.setEnabled(False)

        self.close_button = QPushButton('Close')
        self.close_button.clicked.connect(self.close)

        button_layout.addWidget(self.check_button)
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.restart_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_settings(self):
        """Load saved update preferences."""
        preferred_branch = self.settings.value('update_branch', 'main')
        if preferred_branch == 'development':
            self.development_radio.setChecked(True)
        else:
            self.main_radio.setChecked(True)

    def save_settings(self):
        """Save update preferences."""
        branch = 'development' if self.development_radio.isChecked() else 'main'
        self.settings.setValue('update_branch', branch)

    def get_selected_branch(self) -> str:
        """
        Get the currently selected branch.

        Returns:
            Branch name ('main' or 'development')
        """
        return 'development' if self.development_radio.isChecked() else 'main'

    def check_for_updates(self):
        """Check for available updates from GitHub."""
        self.save_settings()

        # Show backup warning
        reply = QMessageBox.question(
            self,
            'Backup Recommended',
            'It is recommended to backup your database before updating.\n\n'
            'You can backup the database from the Maintenance tab.\n\n'
            'Do you want to continue checking for updates?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Disable controls during check
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.main_radio.setEnabled(False)
        self.development_radio.setEnabled(False)

        # Clear previous status
        self.status_text.clear()
        self.status_text.append("Checking for updates...\n")

        # Start background check
        branch = self.get_selected_branch()
        self.check_worker = UpdateCheckWorker(branch)
        self.check_worker.progress.connect(self.on_check_progress)
        self.check_worker.finished.connect(self.on_check_finished)
        self.check_worker.start()

    def on_check_progress(self, message: str):
        """
        Handle progress messages from update check.

        Args:
            message: Progress message to display
        """
        self.status_text.append(message)

    def on_check_finished(self, result: dict):
        """
        Handle completion of update check.

        Args:
            result: Dictionary with update information
        """
        # Re-enable controls
        self.check_button.setEnabled(True)
        self.main_radio.setEnabled(True)
        self.development_radio.setEnabled(True)

        self.update_info = result

        if result.get('error'):
            self.status_text.append(f"\nError: {result['error']}")
            return

        # Display update information
        self.status_text.append(f"\nBranch: {result['branch']}")
        self.status_text.append(f"Latest commit: {result['latest_version']}")
        self.status_text.append(f"Date: {result['commit_date']}")
        self.status_text.append(f"Message: {result['commit_message']}")

        if result['update_available']:
            self.status_text.append("\nUpdate available!")
            self.download_button.setEnabled(True)
        else:
            self.status_text.append("\nYou are up to date!")

    def download_and_install(self):
        """Download and install the update."""
        # Confirm action
        reply = QMessageBox.warning(
            self,
            'Install Update',
            'This will download and install the latest version.\n\n'
            'Make sure you have backed up your database!\n\n'
            'The application will need to be restarted after the update.\n\n'
            'Do you want to continue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Disable controls during download
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.main_radio.setEnabled(False)
        self.development_radio.setEnabled(False)
        self.close_button.setEnabled(False)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Clear status
        self.status_text.clear()
        self.status_text.append("Starting download...\n")

        # Start background download
        branch = self.get_selected_branch()
        self.download_worker = UpdateDownloadWorker(branch)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.percent.connect(self.on_download_percent)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()

    def on_download_progress(self, message: str):
        """
        Handle progress messages from download.

        Args:
            message: Progress message to display
        """
        self.status_text.append(message)

    def on_download_percent(self, percent: int):
        """
        Handle download percentage updates.

        Args:
            percent: Download progress (0-100)
        """
        self.progress_bar.setValue(percent)

    def on_download_finished(self, success: bool):
        """
        Handle completion of download and installation.

        Args:
            success: True if update was applied successfully
        """
        # Hide progress bar
        self.progress_bar.setVisible(False)

        # Re-enable close button
        self.close_button.setEnabled(True)

        if success:
            self.status_text.append("\nUpdate installed successfully!")
            self.status_text.append("\nPlease restart the application to use the new version.")
            self.restart_button.setEnabled(True)
        else:
            self.status_text.append("\nUpdate failed. Please try again or update manually.")
            self.check_button.setEnabled(True)
            self.main_radio.setEnabled(True)
            self.development_radio.setEnabled(True)

    def restart_application(self):
        """Restart the application after update."""
        reply = QMessageBox.question(
            self,
            'Restart Application',
            'The application will now restart.\n\n'
            'Make sure all your work is saved.\n\n'
            'Do you want to restart now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            UpdateManager.restart_application()
