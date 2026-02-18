"""
Dialog for importing master frames to a project.

Allows user to select master frames (light or calibration) from the catalog and import them to a project.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QCheckBox, QWidget, QLineEdit
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QBrush

import sqlite3
from typing import List, Optional


class ImportMasterFramesDialog(QDialog):
    """Dialog for importing master frames to a project."""

    def __init__(self, db_path: str, project_id: int, project_name: str,
                 settings: Optional[QSettings] = None, parent=None):
        """
        Initialize import master frames dialog.

        Args:
            db_path: Path to database
            project_id: Project ID to import master frames to
            project_name: Project name (for display)
            settings: QSettings object for storing user preferences (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.project_id = project_id
        self.project_name = project_name
        self.settings = settings  # Store settings for saving/restoring UI preferences
        self.all_frames_data = []  # Store all frames data for filtering

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

        # Filename filter section (issue #217)
        filter_group = QGroupBox("Filter by Filename")
        filter_layout = QHBoxLayout()

        filter_label = QLabel("Filename contains:")
        filter_layout.addWidget(filter_label)

        self.filename_filter_input = QLineEdit()
        self.filename_filter_input.setPlaceholderText("Enter text to filter by filename (case-insensitive)")
        self.filename_filter_input.textChanged.connect(self.apply_filename_filter)
        filter_layout.addWidget(self.filename_filter_input)

        clear_filter_btn = QPushButton("Clear Filter")
        clear_filter_btn.clicked.connect(self.clear_filename_filter)
        filter_layout.addWidget(clear_filter_btn)

        self.filter_status_label = QLabel("")
        filter_layout.addWidget(self.filter_status_label)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

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
        self.frames_table.horizontalHeader().setSectionsMovable(True)
        self.frames_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.frames_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set default column widths or restore from settings
        default_widths = [60, 100, 80, 80, 80, 70, 200, 120]  # Select, Type, Filter, Exposure, Temp, Binning, Filename, Already Imported
        for col in range(8):
            if self.settings:
                saved_width = self.settings.value(f'import_master_frames_dialog_col_{col}')
                if saved_width:
                    self.frames_table.setColumnWidth(col, int(saved_width))
                else:
                    self.frames_table.setColumnWidth(col, default_widths[col])
            else:
                self.frames_table.setColumnWidth(col, default_widths[col])

        # Restore column order from settings
        if self.settings:
            saved_order = self.settings.value('import_master_frames_dialog_col_order')
            if saved_order:
                # Convert to integers (QSettings may return strings)
                saved_order = [int(idx) for idx in saved_order]
                for visual_index, logical_index in enumerate(saved_order):
                    self.frames_table.horizontalHeader().moveSection(
                        self.frames_table.horizontalHeader().visualIndex(logical_index),
                        visual_index
                    )

        # Connect column resize and move to save settings
        if self.settings:
            self.frames_table.horizontalHeader().sectionResized.connect(self.save_column_widths)
            self.frames_table.horizontalHeader().sectionMoved.connect(self.save_column_order)

        # Enable sorting by clicking column headers (will be toggled during data loading)
        self.frames_table.setSortingEnabled(True)

        # Connect sort indicator changed signal to save sort state
        if self.settings:
            self.frames_table.horizontalHeader().sortIndicatorChanged.connect(self.save_sort_state)

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

            # Store all frames data for filtering
            self.all_frames_data = []
            for row in rows:
                (file_id, imagetyp, filter_name, exposure, ccd_temp,
                 xbinning, ybinning, filename, is_imported) = row

                # Determine frame type
                frame_type = "Master Light"
                if "Light" not in imagetyp:
                    frame_type = "Unknown"

                self.all_frames_data.append({
                    'file_id': file_id,
                    'imagetyp': imagetyp,
                    'filter': filter_name,
                    'exposure': exposure,
                    'ccd_temp': ccd_temp,
                    'xbinning': xbinning,
                    'ybinning': ybinning,
                    'filename': filename,
                    'is_imported': is_imported,
                    'frame_type': frame_type
                })

            # Display all frames initially
            self.populate_table(self.all_frames_data)

        finally:
            conn.close()

    def populate_table(self, frames_data: List[dict]):
        """
        Populate the table with the given frames data.

        Args:
            frames_data: List of frame dictionaries to display
        """
        # Populate table
        self.frames_table.setRowCount(len(frames_data))

        for row_idx, frame in enumerate(frames_data):
            # Select checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            if frame['is_imported']:
                checkbox.setEnabled(False)
            checkbox.stateChanged.connect(self.update_selected_count)

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)

            self.frames_table.setCellWidget(row_idx, 0, checkbox_widget)

            # Store file_id in checkbox
            checkbox.setProperty("file_id", frame['file_id'])

            # Type
            self.frames_table.setItem(row_idx, 1, QTableWidgetItem(frame['frame_type']))

            # Filter
            filter_text = frame['filter'] if frame['filter'] else "N/A"
            self.frames_table.setItem(row_idx, 2, QTableWidgetItem(filter_text))

            # Exposure
            exp_text = f"{frame['exposure']:.1f}s" if frame['exposure'] is not None else "N/A"
            self.frames_table.setItem(row_idx, 3, QTableWidgetItem(exp_text))

            # Temperature
            temp_text = f"{frame['ccd_temp']:.1f}" if frame['ccd_temp'] is not None else "N/A"
            self.frames_table.setItem(row_idx, 4, QTableWidgetItem(temp_text))

            # Binning
            binning_text = f"{frame['xbinning']}x{frame['ybinning']}" if frame['xbinning'] and frame['ybinning'] else "N/A"
            self.frames_table.setItem(row_idx, 5, QTableWidgetItem(binning_text))

            # Filename
            self.frames_table.setItem(row_idx, 6, QTableWidgetItem(frame['filename']))

            # Already imported status
            status_item = QTableWidgetItem("Yes" if frame['is_imported'] else "No")
            if frame['is_imported']:
                status_item.setForeground(QBrush(QColor("#5cb85c")))  # Green
            self.frames_table.setItem(row_idx, 7, status_item)

            # Gray out already imported rows
            if frame['is_imported']:
                for col in range(1, 8):
                    item = self.frames_table.item(row_idx, col)
                    if item:
                        item.setForeground(QBrush(QColor("#999999")))

        self.update_selected_count()

    def apply_filename_filter(self):
        """
        Apply filename filter to the table.

        Filters the displayed frames based on the text in the filename filter input.
        Performs case-insensitive substring matching.
        """
        filter_text = self.filename_filter_input.text().strip().lower()

        if not filter_text:
            # No filter - show all frames
            filtered_frames = self.all_frames_data
        else:
            # Filter frames by filename (case-insensitive)
            filtered_frames = [
                frame for frame in self.all_frames_data
                if filter_text in frame['filename'].lower()
            ]

        # Update the table with filtered data
        self.populate_table(filtered_frames)

        # Update filter status label
        if filter_text:
            total_frames = len(self.all_frames_data)
            shown_frames = len(filtered_frames)
            self.filter_status_label.setText(f"Showing {shown_frames} of {total_frames} frames")
        else:
            self.filter_status_label.setText("")

    def clear_filename_filter(self):
        """Clear the filename filter and show all frames."""
        self.filename_filter_input.clear()
        # The textChanged signal will trigger apply_filename_filter()

    def select_all(self):
        """Select all available frames (in the current filtered view)."""
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

    def save_column_widths(self) -> None:
        """Save the table column widths to settings."""
        if not self.settings:
            return

        for col in range(self.frames_table.columnCount()):
            width = self.frames_table.columnWidth(col)
            self.settings.setValue(f'import_master_frames_dialog_col_{col}', width)

    def save_column_order(self) -> None:
        """Save the table column order to settings."""
        if not self.settings:
            return

        header = self.frames_table.horizontalHeader()
        order = [header.logicalIndex(i) for i in range(header.count())]
        self.settings.setValue('import_master_frames_dialog_col_order', order)

    def save_sort_state(self, column: int, order: Qt.SortOrder) -> None:
        """
        Save the table sort state to settings.

        Args:
            column: The column index that is being sorted
            order: The sort order (Qt.SortOrder enum)
        """
        if not self.settings:
            return

        # Save the sort column
        self.settings.setValue('import_master_frames_dialog_sort_column', column)
        # Convert Qt.SortOrder enum to integer: AscendingOrder=0, DescendingOrder=1
        self.settings.setValue('import_master_frames_dialog_sort_order', int(order.value))

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
