"""
Dialog for exporting project files with calibration frames.

Allows user to select destination folder and shows progress during export.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFileDialog, QMessageBox, QLineEdit, QGroupBox,
    QTextBrowser
)
from PyQt6.QtCore import Qt

from core.calibration import CalibrationMatcher
from ui.export_project_worker import ExportProjectWorker


class ExportProjectDialog(QDialog):
    """Dialog for exporting project files."""

    def __init__(self, db_path: str, project_id: int, project_name: str,
                 calibration_matcher: CalibrationMatcher, parent=None):
        """
        Initialize export dialog.

        Args:
            db_path: Path to database
            project_id: Project ID to export
            project_name: Project name (for display)
            calibration_matcher: CalibrationMatcher instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.project_id = project_id
        self.project_name = project_name
        self.calibration_matcher = calibration_matcher
        self.worker = None
        self.destination_path = None

        self.setWindowTitle(f"Checkout Project: {project_name}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.init_ui()

    def init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)

        # Info section
        info_group = QGroupBox("Checkout Information")
        info_layout = QVBoxLayout()

        info_text = QTextBrowser()
        info_text.setMaximumHeight(100)
        info_text.setHtml(f"""
            <p><b>Project:</b> {self.project_name}</p>
            <p>This will copy all light frames from the project along with their matching
            calibration frames (darks, flats, bias) to a destination folder.</p>
            <p>Files will be organized into subdirectories: Lights, Darks, Flats, Bias</p>
        """)
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Destination section
        dest_group = QGroupBox("Destination Folder")
        dest_layout = QVBoxLayout()

        dest_select_layout = QHBoxLayout()
        self.dest_path_edit = QLineEdit()
        self.dest_path_edit.setReadOnly(True)
        self.dest_path_edit.setPlaceholderText("Select destination folder...")
        dest_select_layout.addWidget(self.dest_path_edit)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.select_destination)
        dest_select_layout.addWidget(self.browse_btn)

        dest_layout.addLayout(dest_select_layout)
        dest_group.setLayout(dest_layout)
        layout.addWidget(dest_group)

        # Progress section
        progress_group = QGroupBox("Checkout Progress")
        progress_layout = QVBoxLayout()

        self.status_label = QLabel("Ready to checkout")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)
        progress_layout.addWidget(self.results_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_btn = QPushButton("Start Checkout")
        self.export_btn.clicked.connect(self.start_export)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def select_destination(self):
        """Open folder selection dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Destination Folder",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            self.destination_path = folder
            self.dest_path_edit.setText(folder)
            self.export_btn.setEnabled(True)

    def start_export(self):
        """Start the export process."""
        if not self.destination_path:
            QMessageBox.warning(self, "No Destination", "Please select a destination folder")
            return

        # Disable controls during export
        self.export_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.close_btn.setEnabled(False)

        self.status_label.setText("Starting checkout...")
        self.progress_bar.setValue(0)
        self.results_label.setText("")

        # Create and start worker
        self.worker = ExportProjectWorker(
            self.db_path,
            self.project_id,
            self.destination_path,
            self.calibration_matcher
        )

        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished_successfully.connect(self.on_export_finished)
        self.worker.error_occurred.connect(self.on_export_error)

        self.worker.start()

    def on_progress_updated(self, percent: int, message: str):
        """Update progress bar and status."""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_export_finished(self, light_count: int, dark_count: int,
                          flat_count: int, bias_count: int):
        """Handle successful export completion."""
        self.status_label.setText("Checkout completed successfully!")
        self.progress_bar.setValue(100)

        results_html = f"""
            <b>Files copied:</b><br>
            • Light frames: {light_count}<br>
            • Dark frames: {dark_count}<br>
            • Flat frames: {flat_count}<br>
            • Bias frames: {bias_count}<br>
            <br>
            <b>Total: {light_count + dark_count + flat_count + bias_count} files</b>
        """
        self.results_label.setText(results_html)

        # Re-enable close button
        self.close_btn.setEnabled(True)

        QMessageBox.information(
            self,
            "Checkout Complete",
            f"Successfully checked out {light_count + dark_count + flat_count + bias_count} files\n\n"
            f"Destination: {self.destination_path}"
        )

    def on_export_error(self, error_message: str):
        """Handle export error."""
        self.status_label.setText("Checkout failed")
        self.results_label.setText(f"<span style='color: red;'><b>Error:</b> {error_message}</span>")

        # Re-enable controls
        self.export_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

        QMessageBox.critical(self, "Checkout Failed", error_message)

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Checkout in Progress",
                "Checkout is still in progress. Do you want to cancel and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
