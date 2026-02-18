"""
Dialog for importing master frames to a project.

Allows user to select master frames (light or calibration) from the catalog and import them to a project.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QBrush

import sqlite3
from typing import List


class ImportMasterFramesDialog(QDialog):
    """Dialog for importing master frames to a project."""

    def __init__(self, db_path: str, project_id: int, project_name: str, parent=None):
        """
        Initialize import master frames dialog.

        Args:
            db_path: Path to database
            project_id: Project ID to import master frames to
            project_name: Project name (for display)
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.project_id = project_id
        self.project_name = project_name

        self.setWindowTitle(f"Import Master Frames: {project_name}")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        self.init_ui()
        self.load_master_frames()

        # Restore window geometry from settings
        self.restore_window_geometry()

    def init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)

        # Info section
        info_group = QGroupBox("Import Master Frames")
        info_layout = QVBoxLayout()

        info_label = QLabel(
            f"Select master light frames to import to project: <b>{self.project_name}</b><br>"
            "Master light frames are stacked light frames (the actual deep-sky object images).<br>"
            "These will be displayed in the project details section."
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Note: Filter section removed - only Master Light frames are allowed
        # as per issue #207

        # Master frames table
        frames_group = QGroupBox("Available Master Light Frames")
        frames_layout = QVBoxLayout()

        self.frames_table = QTableWidget()
        self.frames_table.setColumnCount(8)
        self.frames_table.setHorizontalHeaderLabels([
            "Select", "Type", "Filter", "Exposure", "Temp (°C)", "Binning", "Filename", "Already Imported"
        ])

        # Configure table
        self.frames_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.frames_table.horizontalHeader().setStretchLastSection(True)
        self.frames_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.frames_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set column widths
        self.frames_table.setColumnWidth(0, 60)   # Select
        self.frames_table.setColumnWidth(1, 100)  # Type
        self.frames_table.setColumnWidth(2, 80)   # Filter
        self.frames_table.setColumnWidth(3, 80)   # Exposure
        self.frames_table.setColumnWidth(4, 80)   # Temp
        self.frames_table.setColumnWidth(5, 70)   # Binning
        self.frames_table.setColumnWidth(6, 200)  # Filename

        frames_layout.addWidget(self.frames_table)
        frames_group.setLayout(frames_layout)
        layout.addWidget(frames_group)

        # Selection controls
        selection_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        selection_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        selection_layout.addWidget(deselect_all_btn)

        selection_layout.addStretch()

        self.selected_count_label = QLabel("Selected: 0")
        selection_layout.addWidget(self.selected_count_label)

        layout.addLayout(selection_layout)

        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.import_btn = QPushButton("Import Selected")
        self.import_btn.clicked.connect(self.import_selected)
        self.import_btn.setDefault(True)
        button_layout.addWidget(self.import_btn)

        layout.addLayout(button_layout)

    def load_master_frames(self):
        """
        Load available master light frames from the database.

        Only Master Light frames are loaded, as per issue #207.
        Master Light frames are identified by having 'Master' and 'Light' in the imagetyp field.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Query only Master Light frames with import status
            # Filter for frames with 'Master_Light' in imagetyp
            query = '''
                SELECT
                    xf.id,
                    xf.imagetyp,
                    xf.filter,
                    xf.exposure,
                    xf.ccd_temp,
                    xf.xbinning,
                    xf.ybinning,
                    xf.filename,
                    CASE WHEN pmf.id IS NOT NULL THEN 1 ELSE 0 END as is_imported
                FROM xisf_files xf
                LEFT JOIN project_master_frames pmf
                    ON xf.id = pmf.file_id AND pmf.project_id = ?
                WHERE (xf.imagetyp LIKE '%Master_Light%' OR xf.imagetyp LIKE '%Master%Light%')
                    AND xf.object IS NOT NULL
                ORDER BY xf.imagetyp, xf.filter, xf.exposure, xf.ccd_temp
            '''

            cursor.execute(query, (self.project_id,))
            rows = cursor.fetchall()

            # Populate table
            self.frames_table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                (file_id, imagetyp, filter_name, exposure, ccd_temp,
                 xbinning, ybinning, filename, is_imported) = row

                # Select checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(False)
                if is_imported:
                    checkbox.setEnabled(False)
                checkbox.stateChanged.connect(self.update_selected_count)

                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)

                self.frames_table.setCellWidget(row_idx, 0, checkbox_widget)

                # Store file_id in checkbox
                checkbox.setProperty("file_id", file_id)

                # Determine frame type
                # Only Master Light frames are allowed (issue #207)
                frame_type = "Master Light"
                if "Light" not in imagetyp:
                    frame_type = "Unknown"

                # Type
                self.frames_table.setItem(row_idx, 1, QTableWidgetItem(frame_type))

                # Filter
                filter_text = filter_name if filter_name else "N/A"
                self.frames_table.setItem(row_idx, 2, QTableWidgetItem(filter_text))

                # Exposure
                exp_text = f"{exposure:.1f}s" if exposure is not None else "N/A"
                self.frames_table.setItem(row_idx, 3, QTableWidgetItem(exp_text))

                # Temperature
                temp_text = f"{ccd_temp:.1f}" if ccd_temp is not None else "N/A"
                self.frames_table.setItem(row_idx, 4, QTableWidgetItem(temp_text))

                # Binning
                binning_text = f"{xbinning}x{ybinning}" if xbinning and ybinning else "N/A"
                self.frames_table.setItem(row_idx, 5, QTableWidgetItem(binning_text))

                # Filename
                self.frames_table.setItem(row_idx, 6, QTableWidgetItem(filename))

                # Already imported status
                status_item = QTableWidgetItem("Yes" if is_imported else "No")
                if is_imported:
                    status_item.setForeground(QBrush(QColor("#5cb85c")))  # Green
                self.frames_table.setItem(row_idx, 7, status_item)

                # Gray out already imported rows
                if is_imported:
                    for col in range(1, 8):
                        item = self.frames_table.item(row_idx, col)
                        if item:
                            item.setForeground(QBrush(QColor("#999999")))

            self.update_selected_count()

        finally:
            conn.close()

    def select_all(self):
        """Select all available frames."""
        for row in range(self.frames_table.rowCount()):
            checkbox_widget = self.frames_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isEnabled():
                    checkbox.setChecked(True)

    def deselect_all(self):
        """Deselect all frames."""
        for row in range(self.frames_table.rowCount()):
            checkbox_widget = self.frames_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)

    def update_selected_count(self):
        """Update the selected count label."""
        count = 0
        for row in range(self.frames_table.rowCount()):
            checkbox_widget = self.frames_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    count += 1

        self.selected_count_label.setText(f"Selected: {count}")
        self.import_btn.setEnabled(count > 0)

    def import_selected(self):
        """Import the selected master frames."""
        # Collect selected file IDs
        file_ids = []
        for row in range(self.frames_table.rowCount()):
            checkbox_widget = self.frames_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    file_id = checkbox.property("file_id")
                    if file_id:
                        file_ids.append(file_id)

        if not file_ids:
            QMessageBox.warning(self, "No Selection", "Please select at least one master frame to import.")
            return

        # Import master frames using project manager
        try:
            from core.project_manager import ProjectManager
            project_manager = ProjectManager(self.db_path)
            imported_count = project_manager.import_master_frames(self.project_id, file_ids)

            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {imported_count} master frame(s) to the project."
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Failed",
                f"Failed to import master frames:\n{str(e)}"
            )

    def restore_window_geometry(self):
        """
        Restore the window size and position from saved settings.

        If no saved geometry exists, the window will use its default minimum size.
        """
        settings = QSettings('AstroFileManager', 'AstroFileManager')
        geometry = settings.value('import_master_frames_dialog/geometry')
        if geometry:
            self.restoreGeometry(geometry)

    def save_window_geometry(self):
        """Save the current window size and position to settings."""
        settings = QSettings('AstroFileManager', 'AstroFileManager')
        settings.setValue('import_master_frames_dialog/geometry', self.saveGeometry())

    def closeEvent(self, event):
        """
        Handle window close event.

        Saves the window geometry before closing.

        Args:
            event: QCloseEvent object
        """
        self.save_window_geometry()
        super().closeEvent(event)
