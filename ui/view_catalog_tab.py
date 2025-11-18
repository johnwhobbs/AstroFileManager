"""
View Catalog tab UI for the AstroFileManager application.
"""

import os
import sqlite3
import subprocess
import platform
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QLineEdit, QComboBox, QPushButton, QMenu, QMessageBox,
    QFileDialog, QApplication, QProgressBar
)

# Import CSV exporter and catalog worker
from import_export.csv_exporter import CSVExporter
from ui.catalog_worker import CatalogLoaderWorker


class ViewCatalogTab(QWidget):
    """View Catalog tab for displaying and managing the XISF file database."""

    def __init__(self, db_path: str, settings: QSettings,
                 status_callback: Callable[[str], None],
                 reimport_callback: Callable[[List[str]], None]) -> None:
        """
        Initialize the View Catalog tab.

        Args:
            db_path: Path to the SQLite database
            settings: QSettings object for application settings
            status_callback: Callback function to set status messages
            reimport_callback: Callback function to reimport files
        """
        super().__init__()
        self.db_path = db_path
        self.settings = settings
        self.status_callback = status_callback
        self.reimport_callback = reimport_callback
        self.loader_worker = None  # Background thread for loading catalog data
        self.init_ui()

    def init_ui(self) -> None:
        """Create the view tab UI."""
        layout = QVBoxLayout(self)

        # Summary statistics panel
        stats_group = QGroupBox("Database Summary")
        stats_layout = QHBoxLayout()

        # Statistics cards
        self.catalog_total_files_label = QLabel("0")
        self.catalog_total_files_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.catalog_total_files_card = self.create_stat_card("Total Files", self.catalog_total_files_label)
        stats_layout.addWidget(self.catalog_total_files_card)

        self.catalog_total_exposure_label = QLabel("0.0 hrs")
        self.catalog_total_exposure_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.catalog_total_exposure_card = self.create_stat_card("Total Exposure", self.catalog_total_exposure_label)
        stats_layout.addWidget(self.catalog_total_exposure_card)

        self.catalog_objects_label = QLabel("0")
        self.catalog_objects_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.catalog_objects_card = self.create_stat_card("Objects", self.catalog_objects_label)
        stats_layout.addWidget(self.catalog_objects_card)

        self.catalog_breakdown_label = QLabel("L:0 D:0 F:0 B:0")
        self.catalog_breakdown_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.catalog_breakdown_card = self.create_stat_card("Frame Breakdown", self.catalog_breakdown_label)
        stats_layout.addWidget(self.catalog_breakdown_card)

        self.catalog_date_range_label = QLabel("N/A")
        self.catalog_date_range_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.catalog_date_range_card = self.create_stat_card("Date Range", self.catalog_date_range_label)
        stats_layout.addWidget(self.catalog_date_range_card)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Search and filter controls
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Search:"))
        self.catalog_search_box = QLineEdit()
        self.catalog_search_box.setPlaceholderText("Filter by name, object, filter...")
        self.catalog_search_box.textChanged.connect(self.filter_catalog_tree)
        filter_layout.addWidget(self.catalog_search_box)

        filter_layout.addWidget(QLabel("Image Type:"))
        self.catalog_imagetype_filter = QComboBox()
        self.catalog_imagetype_filter.addItems(['All', 'Light', 'Dark', 'Flat', 'Bias', 'Master'])
        self.catalog_imagetype_filter.currentTextChanged.connect(self.refresh_catalog_view)
        filter_layout.addWidget(self.catalog_imagetype_filter)

        filter_layout.addWidget(QLabel("Object:"))
        self.catalog_object_filter = QComboBox()
        self.catalog_object_filter.addItem('All')
        self.catalog_object_filter.currentTextChanged.connect(self.refresh_catalog_view)
        filter_layout.addWidget(self.catalog_object_filter)

        export_btn = QPushButton('Export to CSV')
        export_btn.clicked.connect(self.export_catalog_to_csv)
        filter_layout.addWidget(export_btn)

        refresh_btn = QPushButton('Refresh')
        refresh_btn.clicked.connect(self.refresh_catalog_view)
        filter_layout.addWidget(refresh_btn)

        layout.addLayout(filter_layout)

        # Progress bar and status label for background loading
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.catalog_status_label = QLabel("")
        self.catalog_status_label.setStyleSheet("color: #666; font-style: italic;")
        progress_layout.addWidget(self.catalog_status_label)

        self.catalog_progress = QProgressBar()
        self.catalog_progress.setRange(0, 0)  # Indeterminate progress
        self.catalog_progress.setTextVisible(False)
        self.catalog_progress.setMaximumHeight(4)  # Slim progress bar
        progress_layout.addWidget(self.catalog_progress)

        progress_widget.hide()  # Hidden by default
        self.catalog_progress_widget = progress_widget
        layout.addWidget(progress_widget)

        # Tree widget with expanded columns
        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setColumnCount(9)
        self.catalog_tree.setHeaderLabels([
            'Name', 'Image Type', 'Filter', 'Exposure', 'Temp', 'Binning', 'Date', 'Telescope', 'Instrument'
        ])
        # Set initial column widths
        self.catalog_tree.setColumnWidth(0, 300)
        self.catalog_tree.setColumnWidth(1, 120)
        self.catalog_tree.setColumnWidth(2, 80)
        self.catalog_tree.setColumnWidth(3, 80)
        self.catalog_tree.setColumnWidth(4, 60)
        self.catalog_tree.setColumnWidth(5, 70)
        self.catalog_tree.setColumnWidth(6, 100)
        self.catalog_tree.setColumnWidth(7, 120)
        self.catalog_tree.setColumnWidth(8, 120)

        # Enable context menu
        self.catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.catalog_tree.customContextMenuRequested.connect(self.show_catalog_context_menu)

        layout.addWidget(self.catalog_tree)

    def create_stat_card(self, title: str, value_label: QLabel) -> QWidget:
        """Create a statistics card widget."""
        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #888888; font-size: 11px;")
        card_layout.addWidget(title_label)

        card_layout.addWidget(value_label)

        # Add border and background
        card.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
        """)

        return card

    def filter_catalog_tree(self) -> None:
        """Filter the catalog tree based on search text."""
        search_text = self.catalog_search_box.text().lower()

        def filter_item(item: QTreeWidgetItem) -> bool:
            """Recursively filter tree items."""
            # Check if this item matches
            item_text = ' '.join([item.text(i).lower() for i in range(item.columnCount())])
            matches = search_text in item_text

            # Check children
            child_visible = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    child_visible = True

            # Show item if it matches or has visible children
            visible = matches or child_visible
            item.setHidden(not visible)
            return visible

        # Filter all top-level items
        root = self.catalog_tree.invisibleRootItem()
        for i in range(root.childCount()):
            filter_item(root.child(i))

    def show_catalog_context_menu(self, position) -> None:
        """Show context menu for catalog tree items."""
        item = self.catalog_tree.itemAt(position)
        if not item:
            return

        menu = QMenu()

        # Only show file operations if this is a file item (has no children and is not a group node)
        is_file = item.childCount() == 0 and '(' not in item.text(0)

        if is_file:
            show_path_action = menu.addAction("Show Full Path")
            copy_path_action = menu.addAction("Copy Path to Clipboard")
            open_location_action = menu.addAction("Open File Location")
            menu.addSeparator()
            show_details_action = menu.addAction("Show File Details")
            menu.addSeparator()
            delete_action = menu.addAction("Delete from Database")
            reimport_action = menu.addAction("Re-import File")

            action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

            if action == show_path_action:
                self.show_file_path(item)
            elif action == copy_path_action:
                self.copy_file_path_to_clipboard(item)
            elif action == open_location_action:
                self.open_file_location(item)
            elif action == show_details_action:
                self.show_file_details(item)
            elif action == delete_action:
                self.delete_file_from_database(item)
            elif action == reimport_action:
                self.reimport_file(item)
        else:
            # For group nodes, offer export
            export_action = menu.addAction("Export This Group to CSV")
            action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

            if action == export_action:
                self.export_tree_group_to_csv(item)

    def show_file_path(self, item: QTreeWidgetItem) -> None:
        """Show the full file path in a message box."""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                QMessageBox.information(self, 'File Path', f'Full path:\n{result[0]}')
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to retrieve file path: {e}')

    def copy_file_path_to_clipboard(self, item: QTreeWidgetItem) -> None:
        """Copy file path to clipboard."""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                clipboard = QApplication.clipboard()
                clipboard.setText(result[0])
                self.status_callback(f'Path copied to clipboard: {filename}')
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to copy path: {e}')

    def open_file_location(self, item: QTreeWidgetItem) -> None:
        """Open the file location in file manager."""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                filepath = result[0]
                directory = os.path.dirname(filepath)

                if platform.system() == 'Windows':
                    subprocess.run(['explorer', '/select,', filepath])
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', '-R', filepath])
                else:  # Linux
                    subprocess.run(['xdg-open', directory])
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to open file location: {e}')

    def show_file_details(self, item: QTreeWidgetItem) -> None:
        """Show detailed file information in a dialog."""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT filepath, telescop, instrume, object, filter, imagetyp,
                       exposure, ccd_temp, xbinning, ybinning, date_loc, created_at
                FROM xisf_files
                WHERE filename = ?
            ''', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                exposure_str = f"{result[6]:.1f}s" if result[6] else 'N/A'
                temp_str = f"{result[7]:.1f}°C" if result[7] is not None else 'N/A'
                binning_str = f"{int(result[8])}x{int(result[9])}" if result[8] and result[9] else 'N/A'

                details = f"""File: {filename}
Path: {result[0]}

Telescope: {result[1] or 'N/A'}
Instrument: {result[2] or 'N/A'}
Object: {result[3] or 'N/A'}
Filter: {result[4] or 'N/A'}
Image Type: {result[5] or 'N/A'}
Exposure: {exposure_str}
Temperature: {temp_str}
Binning: {binning_str}
Date: {result[10] or 'N/A'}
Imported: {result[11] or 'N/A'}
"""
                QMessageBox.information(self, 'File Details', details)
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to retrieve file details: {e}')

    def delete_file_from_database(self, item: QTreeWidgetItem) -> None:
        """Delete a file from the database."""
        filename = item.text(0)
        reply = QMessageBox.question(
            self, 'Confirm Delete',
            f'Are you sure you want to delete "{filename}" from the database?\n\nNote: This will not delete the actual file.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM xisf_files WHERE filename = ?', (filename,))
                conn.commit()
                conn.close()

                QMessageBox.information(self, 'Success', f'File deleted from database: {filename}')
                self.refresh_catalog_view()
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to delete file: {e}')

    def reimport_file(self, item: QTreeWidgetItem) -> None:
        """Re-import a file."""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                filepath = result[0]
                if os.path.exists(filepath):
                    self.reimport_callback([filepath])
                else:
                    QMessageBox.warning(self, 'File Not Found', f'File does not exist:\n{filepath}')
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to re-import file: {e}')

    def export_tree_group_to_csv(self, item: QTreeWidgetItem) -> None:
        """Export a tree group (and its children) to CSV."""
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Export Group to CSV', '', 'CSV Files (*.csv)'
        )

        if not filename:
            return

        try:
            CSVExporter.export_tree_group(filename, item)
            QMessageBox.information(self, 'Success', f'Exported group to:\n{filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export: {e}')

    def export_catalog_to_csv(self) -> None:
        """Export entire catalog to CSV."""
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Export Catalog to CSV', '', 'CSV Files (*.csv)'
        )

        if not filename:
            return

        try:
            row_count = CSVExporter.export_catalog(filename, self.db_path)
            QMessageBox.information(self, 'Success', f'Exported {row_count} files to:\n{filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export: {e}')

    def update_catalog_statistics(self, cursor) -> None:
        """Update the catalog statistics panel."""
        # Total files
        cursor.execute('SELECT COUNT(*) FROM xisf_files')
        total_files = cursor.fetchone()[0]
        self.catalog_total_files_label.setText(str(total_files))

        # Total exposure (light frames only)
        cursor.execute('''
            SELECT SUM(exposure) / 3600.0
            FROM xisf_files
            WHERE (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                AND exposure IS NOT NULL
        ''')
        total_exposure = cursor.fetchone()[0] or 0
        self.catalog_total_exposure_label.setText(f"{total_exposure:.1f} hrs")

        # Total objects
        cursor.execute('SELECT COUNT(DISTINCT object) FROM xisf_files WHERE object IS NOT NULL')
        total_objects = cursor.fetchone()[0]
        self.catalog_objects_label.setText(str(total_objects))

        # Frame breakdown
        cursor.execute('''
            SELECT
                SUM(CASE WHEN imagetyp LIKE '%Light%' THEN 1 ELSE 0 END) as lights,
                SUM(CASE WHEN imagetyp LIKE '%Dark%' THEN 1 ELSE 0 END) as darks,
                SUM(CASE WHEN imagetyp LIKE '%Flat%' THEN 1 ELSE 0 END) as flats,
                SUM(CASE WHEN imagetyp LIKE '%Bias%' THEN 1 ELSE 0 END) as bias
            FROM xisf_files
        ''')
        lights, darks, flats, bias = cursor.fetchone()
        self.catalog_breakdown_label.setText(f"L:{lights or 0} D:{darks or 0} F:{flats or 0} B:{bias or 0}")

        # Date range
        cursor.execute('''
            SELECT MIN(date_loc), MAX(date_loc)
            FROM xisf_files
            WHERE date_loc IS NOT NULL
        ''')
        min_date, max_date = cursor.fetchone()
        if min_date and max_date:
            if min_date == max_date:
                self.catalog_date_range_label.setText(min_date)
            else:
                self.catalog_date_range_label.setText(f"{min_date} to {max_date}")
        else:
            self.catalog_date_range_label.setText("N/A")

    def get_item_color(self, imagetyp: Optional[str]) -> Optional[QColor]:
        """Get color for tree item based on image type."""
        if not imagetyp:
            return None

        imagetyp_lower = imagetyp.lower()

        # Master frames - purple/magenta
        if 'master' in imagetyp_lower:
            return QColor(200, 150, 255)  # Light purple

        # Regular frames
        if 'light' in imagetyp_lower:
            return QColor(200, 255, 200)  # Light green
        elif 'dark' in imagetyp_lower:
            return QColor(220, 220, 255)  # Light blue
        elif 'flat' in imagetyp_lower:
            return QColor(255, 240, 200)  # Light orange/yellow
        elif 'bias' in imagetyp_lower:
            return QColor(255, 220, 220)  # Light red/pink

        return None

    def refresh_catalog_view(self) -> None:
        """Refresh the catalog view tree with optimized single-query approach."""
        try:
            # Show loading cursor
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Update summary statistics
            self.update_catalog_statistics(cursor)

            # Populate object filter dropdown
            cursor.execute('''
                SELECT DISTINCT object
                FROM xisf_files
                WHERE object IS NOT NULL
                ORDER BY object
            ''')
            objects = [row[0] for row in cursor.fetchall()]

            # Save current selection
            current_object = self.catalog_object_filter.currentText()

            # Update dropdown
            self.catalog_object_filter.blockSignals(True)
            self.catalog_object_filter.clear()
            self.catalog_object_filter.addItem('All')
            self.catalog_object_filter.addItems(objects)

            # Restore selection if still available
            if current_object in ['All'] + objects:
                self.catalog_object_filter.setCurrentText(current_object)

            self.catalog_object_filter.blockSignals(False)

            # Get filter values
            imagetype_filter = self.catalog_imagetype_filter.currentText()
            object_filter = self.catalog_object_filter.currentText()

            # Disable tree updates during population for better performance
            self.catalog_tree.setUpdatesEnabled(False)
            self.catalog_tree.clear()

            # ===== LIGHT FRAMES SECTION =====
            # Skip light frames section if filtering to calibration only
            if imagetype_filter not in ['Dark', 'Flat', 'Bias', 'Master']:
                self._build_light_frames_tree_optimized(cursor, imagetype_filter, object_filter)

            # ===== CALIBRATION FRAMES SECTION =====
            # Skip calibration frames if filtering to Light only
            if imagetype_filter not in ['Light']:
                self._build_calibration_frames_tree_optimized(cursor, imagetype_filter)

            conn.close()

            # Re-enable tree updates
            self.catalog_tree.setUpdatesEnabled(True)

            # Restore cursor
            QApplication.restoreOverrideCursor()

            # Don't expand any items by default - keep everything collapsed

        except Exception as e:
            # Restore cursor and tree updates on error
            QApplication.restoreOverrideCursor()
            self.catalog_tree.setUpdatesEnabled(True)
            QMessageBox.critical(self, 'Error', f'Failed to refresh view: {e}')

    def _build_light_frames_tree_optimized(self, cursor, imagetype_filter: str, object_filter: str) -> None:
        """Build light frames tree using single hierarchical query (OPTIMIZED)."""
        # Build filter conditions
        where_conditions = ['object IS NOT NULL']
        params = []
    
        if object_filter != 'All':
            where_conditions.append('object = ?')
            params.append(object_filter)
    
        if imagetype_filter == 'Light':
            where_conditions.append('imagetyp LIKE ?')
            params.append('%Light%')
        elif imagetype_filter == 'Master':
            where_conditions.append('imagetyp LIKE ?')
            params.append('%Master%')
    
        where_clause = ' AND '.join(where_conditions)
    
        # Get total light frame counts for root node
        cursor.execute(f'''
            SELECT COUNT(*), SUM(exposure) / 3600.0
            FROM xisf_files
            WHERE {where_clause}
        ''', params)
        light_total_count, light_total_exp = cursor.fetchone()
        light_total_exp = light_total_exp or 0
    
        if light_total_count == 0:
            return
    
        light_frames_root = QTreeWidgetItem(self.catalog_tree)
        light_frames_root.setText(0, f"Light Frames ({light_total_count} files, {light_total_exp:.1f}h)")
        light_frames_root.setFlags(light_frames_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
        font = light_frames_root.font(0)
        font.setBold(True)
        light_frames_root.setFont(0, font)
    
        # SINGLE HIERARCHICAL QUERY - fetch all light frame data sorted hierarchically
        cursor.execute(f'''
            SELECT
                object,
                filter,
                date_loc,
                filename,
                imagetyp,
                exposure,
                ccd_temp,
                xbinning,
                ybinning,
                telescop,
                instrume
            FROM xisf_files
            WHERE {where_clause}
            ORDER BY object, filter NULLS FIRST, date_loc DESC, filename
        ''', params)
    
        # Build tree in single pass using state tracking
        current_obj = None
        current_filter = None
        current_date = None
    
        obj_item = None
        filter_item = None
        date_item = None
    
        # Aggregation tracking
        obj_files = {}  # object -> {count, exposure}
        filter_files = {}  # (object, filter) -> {count, exposure}
        date_files = {}  # (object, filter, date) -> {count, exposure}
    
        # First pass: aggregate counts
        all_rows = cursor.fetchall()
        for row in all_rows:
            obj, filt, date_loc, filename, imagetyp, exposure, temp, xbin, ybin, telescop, instrume = row
    
            # Aggregate by object
            if obj not in obj_files:
                obj_files[obj] = {'count': 0, 'exposure': 0}
            obj_files[obj]['count'] += 1
            obj_files[obj]['exposure'] += (exposure or 0)
    
            # Aggregate by filter
            key_filter = (obj, filt)
            if key_filter not in filter_files:
                filter_files[key_filter] = {'count': 0, 'exposure': 0}
            filter_files[key_filter]['count'] += 1
            filter_files[key_filter]['exposure'] += (exposure or 0)
    
            # Aggregate by date
            key_date = (obj, filt, date_loc)
            if key_date not in date_files:
                date_files[key_date] = {'count': 0, 'exposure': 0}
            date_files[key_date]['count'] += 1
            date_files[key_date]['exposure'] += (exposure or 0)
    
        # Second pass: build tree
        for row in all_rows:
            obj, filt, date_loc, filename, imagetyp, exposure, temp, xbin, ybin, telescop, instrume = row
    
            # Create object node if new
            if obj != current_obj:
                obj_stats = obj_files[obj]
                obj_exp_hrs = obj_stats['exposure'] / 3600.0
                obj_item = QTreeWidgetItem(light_frames_root)
                obj_item.setText(0, f"{obj or 'Unknown'} ({obj_stats['count']} files, {obj_exp_hrs:.1f}h)")
                obj_item.setFlags(obj_item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
                current_obj = obj
                current_filter = None
                current_date = None
    
            # Create filter node if new
            if filt != current_filter:
                filter_stats = filter_files[(obj, filt)]
                filter_exp_hrs = filter_stats['exposure'] / 3600.0
                filter_item = QTreeWidgetItem(obj_item)
                filter_item.setText(0, f"{filt or 'No Filter'} ({filter_stats['count']} files, {filter_exp_hrs:.1f}h)")
                filter_item.setText(2, filt or 'No Filter')
                current_filter = filt
                current_date = None
    
            # Create date node if new
            if date_loc != current_date:
                date_stats = date_files[(obj, filt, date_loc)]
                date_exp_hrs = date_stats['exposure'] / 3600.0
                date_item = QTreeWidgetItem(filter_item)
                date_item.setText(0, f"{date_loc or 'No Date'} ({date_stats['count']} files, {date_exp_hrs:.1f}h)")
                date_item.setText(6, date_loc or 'No Date')
                current_date = date_loc
    
            # Add file node
            file_item = QTreeWidgetItem(date_item)
            file_item.setText(0, filename)
            file_item.setText(1, imagetyp or 'N/A')
            file_item.setText(2, filt or 'N/A')
            file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
            file_item.setText(4, f"{temp:.1f}°C" if temp is not None else 'N/A')
            binning = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
            file_item.setText(5, binning)
            file_item.setText(6, date_loc or 'N/A')
            file_item.setText(7, telescop or 'N/A')
            file_item.setText(8, instrume or 'N/A')
    
            # Apply color coding
            color = self.get_item_color(imagetyp)
            if color:
                for col in range(9):
                    file_item.setBackground(col, QBrush(color))
    
    
    def _build_calibration_frames_tree_optimized(self, cursor, imagetype_filter: str) -> None:
        """Build calibration frames tree using optimized queries."""
        # Get total calibration counts
        calib_where = []
        calib_params = []
    
        if imagetype_filter in ['Dark', 'Flat', 'Bias', 'Master']:
            if imagetype_filter == 'Master':
                calib_where.append('imagetyp LIKE ?')
                calib_params.append('%Master%')
            else:
                calib_where.append('imagetyp LIKE ?')
                calib_params.append(f'%{imagetype_filter}%')
    
        calib_where_clause = 'object IS NULL'
        if calib_where:
            calib_where_clause += ' AND ' + ' AND '.join(calib_where)
    
        cursor.execute(f'''
            SELECT COUNT(*)
            FROM xisf_files
            WHERE {calib_where_clause}
        ''', calib_params)
        calib_total_count = cursor.fetchone()[0]
    
        if calib_total_count == 0:
            return
    
        calib_root = QTreeWidgetItem(self.catalog_tree)
        calib_root.setText(0, f"Calibration Frames ({calib_total_count} files)")
        calib_root.setFlags(calib_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
        font = calib_root.font(0)
        font.setBold(True)
        calib_root.setFont(0, font)
    
        # ----- DARK FRAMES -----
        if imagetype_filter in ['All', 'Dark', 'Master']:
            self._build_darks_tree_optimized(cursor, calib_root, imagetype_filter)
    
        # ----- FLAT FRAMES -----
        if imagetype_filter in ['All', 'Flat', 'Master']:
            self._build_flats_tree_optimized(cursor, calib_root, imagetype_filter)
    
        # ----- BIAS FRAMES -----
        if imagetype_filter in ['All', 'Bias', 'Master']:
            self._build_bias_tree_optimized(cursor, calib_root, imagetype_filter)
    
    
    def _build_darks_tree_optimized(self, cursor, calib_root, imagetype_filter: str) -> None:
        """Build darks tree with single hierarchical query."""
        dark_where = 'imagetyp LIKE "%Dark%" AND object IS NULL'
        if imagetype_filter == 'Master':
            dark_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Dark%" AND object IS NULL'
    
        cursor.execute(f'SELECT COUNT(*) FROM xisf_files WHERE {dark_where}')
        dark_count = cursor.fetchone()[0]
    
        if dark_count == 0:
            return
    
        dark_root = QTreeWidgetItem(calib_root)
        dark_root.setText(0, f"Dark Frames ({dark_count} files)")
        dark_root.setFlags(dark_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
    
        # SINGLE QUERY: Get all darks sorted hierarchically
        cursor.execute(f'''
            SELECT
                exposure,
                ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                xbinning,
                ybinning,
                date_loc,
                filename,
                imagetyp,
                telescop,
                instrume,
                ccd_temp as actual_temp
            FROM xisf_files
            WHERE {dark_where}
            ORDER BY exposure, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, date_loc DESC, filename
        ''')
    
        current_group = None
        current_date = None
        group_item = None
        date_item = None
    
        for row in cursor.fetchall():
            exp, temp, xbin, ybin, date_loc, filename, imagetyp, telescop, instrume, actual_temp = row
    
            # Create dark group node if new
            group_key = (exp, temp, xbin, ybin)
            if group_key != current_group:
                exp_str = f"{int(exp)}s" if exp else "0s"
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
    
                group_item = QTreeWidgetItem(dark_root)
                group_item.setText(0, f"{exp_str}_{temp_str}_{binning}")
                group_item.setText(3, exp_str)
                group_item.setText(4, temp_str)
                group_item.setText(5, binning)
    
                current_group = group_key
                current_date = None
    
            # Create date node if new
            if date_loc != current_date:
                date_item = QTreeWidgetItem(group_item)
                date_item.setText(0, date_loc or 'No Date')
                current_date = date_loc
    
            # Add file node
            file_item = QTreeWidgetItem(date_item)
            file_item.setText(0, filename)
            file_item.setText(1, imagetyp or 'N/A')
            file_item.setText(3, f"{exp:.1f}s" if exp else 'N/A')
            file_item.setText(4, f"{actual_temp:.1f}°C" if actual_temp is not None else 'N/A')
            binning_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
            file_item.setText(5, binning_str)
            file_item.setText(6, date_loc or 'N/A')
            file_item.setText(7, telescop or 'N/A')
            file_item.setText(8, instrume or 'N/A')
    
            color = self.get_item_color(imagetyp)
            if color:
                for col in range(9):
                    file_item.setBackground(col, QBrush(color))
    
    
    def _build_flats_tree_optimized(self, cursor, calib_root, imagetype_filter: str) -> None:
        """Build flats tree with single hierarchical query."""
        flat_where = 'imagetyp LIKE "%Flat%" AND object IS NULL'
        if imagetype_filter == 'Master':
            flat_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Flat%" AND object IS NULL'
    
        cursor.execute(f'SELECT COUNT(*) FROM xisf_files WHERE {flat_where}')
        flat_count = cursor.fetchone()[0]
    
        if flat_count == 0:
            return
    
        flat_root = QTreeWidgetItem(calib_root)
        flat_root.setText(0, f"Flat Frames ({flat_count} files)")
        flat_root.setFlags(flat_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
    
        # SINGLE QUERY: Get all flats sorted hierarchically
        cursor.execute(f'''
            SELECT
                date_loc,
                filter,
                ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                xbinning,
                ybinning,
                filename,
                imagetyp,
                exposure,
                telescop,
                instrume,
                ccd_temp as actual_temp
            FROM xisf_files
            WHERE {flat_where}
            ORDER BY date_loc DESC, filter NULLS FIRST, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, filename
        ''')
    
        current_date = None
        current_group = None
        date_item = None
        group_item = None
    
        for row in cursor.fetchall():
            date_loc, filt, temp, xbin, ybin, filename, imagetyp, exposure, telescop, instrume, actual_temp = row
    
            # Create date node if new
            if date_loc != current_date:
                date_item = QTreeWidgetItem(flat_root)
                date_item.setText(0, date_loc or 'No Date')
                current_date = date_loc
                current_group = None
    
            # Create filter/temp/binning group node if new
            group_key = (filt, temp, xbin, ybin)
            if group_key != current_group:
                filt_str = filt or "NoFilter"
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
    
                group_item = QTreeWidgetItem(date_item)
                group_item.setText(0, f"{filt_str}_{temp_str}_{binning}")
                group_item.setText(2, filt_str)
                group_item.setText(4, temp_str)
                group_item.setText(5, binning)
    
                current_group = group_key
    
            # Add file node
            file_item = QTreeWidgetItem(group_item)
            file_item.setText(0, filename)
            file_item.setText(1, imagetyp or 'N/A')
            file_item.setText(2, filt or 'N/A')
            file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
            file_item.setText(4, f"{actual_temp:.1f}°C" if actual_temp is not None else 'N/A')
            binning_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
            file_item.setText(5, binning_str)
            file_item.setText(6, date_loc or 'N/A')
            file_item.setText(7, telescop or 'N/A')
            file_item.setText(8, instrume or 'N/A')
    
            color = self.get_item_color(imagetyp)
            if color:
                for col in range(9):
                    file_item.setBackground(col, QBrush(color))
    
    
    def _build_bias_tree_optimized(self, cursor, calib_root, imagetype_filter: str) -> None:
        """Build bias tree with single hierarchical query."""
        bias_where = 'imagetyp LIKE "%Bias%" AND object IS NULL'
        if imagetype_filter == 'Master':
            bias_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Bias%" AND object IS NULL'
    
        cursor.execute(f'SELECT COUNT(*) FROM xisf_files WHERE {bias_where}')
        bias_count = cursor.fetchone()[0]
    
        if bias_count == 0:
            return
    
        bias_root = QTreeWidgetItem(calib_root)
        bias_root.setText(0, f"Bias Frames ({bias_count} files)")
        bias_root.setFlags(bias_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
    
        # SINGLE QUERY: Get all bias sorted hierarchically
        cursor.execute(f'''
            SELECT
                ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                xbinning,
                ybinning,
                date_loc,
                filename,
                imagetyp,
                exposure,
                telescop,
                instrume,
                ccd_temp as actual_temp,
                filter
            FROM xisf_files
            WHERE {bias_where}
            ORDER BY ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, date_loc DESC, filename
        ''')
    
        current_group = None
        current_date = None
        group_item = None
        date_item = None
    
        for row in cursor.fetchall():
            temp, xbin, ybin, date_loc, filename, imagetyp, exposure, telescop, instrume, actual_temp, filt = row
    
            # Create bias group node if new
            group_key = (temp, xbin, ybin)
            if group_key != current_group:
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
    
                group_item = QTreeWidgetItem(bias_root)
                group_item.setText(0, f"{temp_str}_{binning}")
                group_item.setText(4, temp_str)
                group_item.setText(5, binning)
    
                current_group = group_key
                current_date = None
    
            # Create date node if new
            if date_loc != current_date:
                date_item = QTreeWidgetItem(group_item)
                date_item.setText(0, date_loc or 'No Date')
                current_date = date_loc
    
            # Add file node
            file_item = QTreeWidgetItem(date_item)
            file_item.setText(0, filename)
            file_item.setText(1, imagetyp or 'N/A')
            file_item.setText(2, filt or 'N/A')
            file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
            file_item.setText(4, f"{actual_temp:.1f}°C" if actual_temp is not None else 'N/A')
            binning_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
            file_item.setText(5, binning_str)
            file_item.setText(6, date_loc or 'N/A')
            file_item.setText(7, telescop or 'N/A')
            file_item.setText(8, instrume or 'N/A')
    
            color = self.get_item_color(imagetyp)
            if color:
                for col in range(9):
                    file_item.setBackground(col, QBrush(color))
