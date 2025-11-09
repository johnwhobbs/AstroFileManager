"""
Import tab UI for AstroFileManager.

This module contains the ImportTab class which handles the UI and logic
for importing XISF files into the database.
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QMessageBox, QProgressBar, QLabel, QTextEdit, QGroupBox,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import QSettings

from import_export.import_worker import ImportWorker


class ImportTab(QWidget):
    """Import tab for XISF file import functionality."""

    def __init__(self, db_path: str, settings: QSettings, clear_db_btn=None):
        """
        Initialize Import tab.

        Args:
            db_path: Path to SQLite database
            settings: QSettings instance for app settings
            clear_db_btn: Reference to clear database button (optional)
        """
        super().__init__()
        self.db_path = db_path
        self.settings = settings
        self.clear_db_btn = clear_db_btn
        self.worker = None

        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Database info
        db_label = QLabel(f"Database: {self.db_path}")
        layout.addWidget(db_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.import_files_btn = QPushButton('Import XISF Files')
        self.import_files_btn.clicked.connect(self.import_files)
        button_layout.addWidget(self.import_files_btn)

        self.import_folder_btn = QPushButton('Import Folder')
        self.import_folder_btn.clicked.connect(self.import_folder)
        button_layout.addWidget(self.import_folder_btn)

        layout.addLayout(button_layout)

        # Import Mode Selection
        import_mode_group = QGroupBox("Import Mode")
        import_mode_layout = QVBoxLayout()

        self.import_mode_button_group = QButtonGroup()
        self.import_only_radio = QRadioButton("Import only (store original paths)")
        self.import_organize_radio = QRadioButton("Import and organize (copy to repository)")

        self.import_mode_button_group.addButton(self.import_only_radio, 0)
        self.import_mode_button_group.addButton(self.import_organize_radio, 1)

        import_mode_layout.addWidget(self.import_only_radio)

        organize_help = QLabel("Copies files to organized folder structure in repository location.")
        organize_help.setStyleSheet("color: #888888; font-size: 10px; margin-left: 20px;")
        import_mode_layout.addWidget(self.import_organize_radio)
        import_mode_layout.addWidget(organize_help)

        # Set default mode from settings
        import_mode = self.settings.value('import_mode', 'import_only')
        if import_mode == 'import_organize':
            self.import_organize_radio.setChecked(True)
        else:
            self.import_only_radio.setChecked(True)

        # Connect signal to save setting
        self.import_mode_button_group.buttonClicked.connect(self.save_import_mode)

        import_mode_group.setLayout(import_mode_layout)
        layout.addWidget(import_mode_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel('')
        layout.addWidget(self.status_label)

        # Log area
        log_label = QLabel('Import Log:')
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def save_import_mode(self):
        """Save the selected import mode."""
        if self.import_organize_radio.isChecked():
            mode = 'import_organize'
        else:
            mode = 'import_only'
        self.settings.setValue('import_mode', mode)

    def import_files(self):
        """Import individual XISF files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Select XISF Files', '', 'XISF Files (*.xisf)'
        )

        if files:
            self.start_import(files)

    def import_folder(self):
        """Import all XISF files from a folder and its subfolders."""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')

        if folder:
            # Recursively find all .xisf files in folder and subfolders
            files = list(Path(folder).rglob('*.xisf'))
            if files:
                self.start_import([str(f) for f in files])
            else:
                QMessageBox.warning(self, 'No Files', 'No XISF files found in selected folder or its subfolders.')

    def start_import(self, files):
        """Start the import worker thread."""
        if not os.path.exists(self.db_path):
            QMessageBox.critical(
                self, 'Database Error',
                f'Database not found: {self.db_path}\nPlease create it first.'
            )
            return

        self.log_text.clear()
        self.log_text.append(f"Starting import of {len(files)} files...\n")

        # Disable buttons
        self.import_files_btn.setEnabled(False)
        self.import_folder_btn.setEnabled(False)
        if self.clear_db_btn:
            self.clear_db_btn.setEnabled(False)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setValue(0)

        # Create and start worker
        timezone = self.settings.value('timezone', 'UTC')

        # Check import mode
        import_mode = self.settings.value('import_mode', 'import_only')
        organize = (import_mode == 'import_organize')
        repo_path = self.settings.value('repository_path', '') if organize else None

        # Warn if organize mode but no repository path
        if organize and not repo_path:
            QMessageBox.warning(
                self, 'No Repository Path',
                'Import and organize mode is selected, but repository path is not set.\n\n'
                'Files will be imported with original paths.\n\n'
                'Set repository path in Settings tab to enable organization during import.'
            )
            organize = False
            repo_path = None

        # Log import mode
        if organize:
            self.log_text.append(f"Import mode: Organize files to repository\n")
            self.log_text.append(f"Repository: {repo_path}\n")
        else:
            self.log_text.append(f"Import mode: Store original paths\n")

        self.worker = ImportWorker(files, self.db_path, timezone, organize, repo_path)
        self.worker.progress.connect(self.on_import_progress)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.start()

    def on_import_progress(self, current, total, message):
        """Handle progress updates."""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing {current}/{total}")
        self.log_text.append(message)

    def on_import_finished(self, processed, errors):
        """Handle import completion."""
        self.progress_bar.setVisible(False)
        self.status_label.setText('')

        self.log_text.append(f"\n{'='*60}")
        self.log_text.append(f"Import complete!")
        self.log_text.append(f"Successfully processed: {processed}")
        self.log_text.append(f"Errors: {errors}")

        # Re-enable buttons
        self.import_files_btn.setEnabled(True)
        self.import_folder_btn.setEnabled(True)
        if self.clear_db_btn:
            self.clear_db_btn.setEnabled(True)

        QMessageBox.information(
            self, 'Import Complete',
            f'Successfully processed: {processed}\nErrors: {errors}'
        )
