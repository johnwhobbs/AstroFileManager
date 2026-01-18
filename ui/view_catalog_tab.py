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

# Import CSV exporter and background workers
from import_export.csv_exporter import CSVExporter
from ui.background_workers import CatalogLoaderWorker
from ui.assign_session_dialog import AssignSessionDialog
from core.project_manager import ProjectManager


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
        self.loader_worker = None  # Background thread for loading catalog
        self.light_data_cache = []  # Cache for lazy loading light frames
        self.project_manager = ProjectManager(db_path)  # For session assignment operations
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

        filter_layout.addWidget(QLabel("Approval:"))
        self.catalog_approval_filter = QComboBox()
        self.catalog_approval_filter.addItems(['All', 'Approved', 'Rejected', 'Not Graded'])
        self.catalog_approval_filter.currentTextChanged.connect(self.refresh_catalog_view)
        filter_layout.addWidget(self.catalog_approval_filter)

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

        # Progress indicator for background loading
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(2)

        self.catalog_status_label = QLabel("")
        self.catalog_status_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        progress_layout.addWidget(self.catalog_status_label)

        self.catalog_progress = QProgressBar()
        self.catalog_progress.setRange(0, 0)  # Indeterminate progress
        self.catalog_progress.setTextVisible(False)
        self.catalog_progress.setMaximumHeight(3)  # Very slim progress bar
        progress_layout.addWidget(self.catalog_progress)

        progress_widget.hide()  # Hidden by default
        self.catalog_progress_widget = progress_widget
        layout.addWidget(progress_widget)

        # Tree widget with expanded columns
        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setColumnCount(14)
        self.catalog_tree.setHeaderLabels([
            'Name', 'Image Type', 'Filter', 'Exposure', 'Temp', 'Binning', 'Date',
            'FWHM', 'Ecc', 'SNR', 'Stars', 'Status', 'Telescope', 'Instrument'
        ])

        # Make columns resizable and movable
        self.catalog_tree.header().setSectionsMovable(True)
        self.catalog_tree.header().setStretchLastSection(True)

        # Set initial column widths or restore from settings
        default_widths = [300, 120, 80, 80, 60, 70, 100, 70, 60, 60, 60, 80, 120, 120]
        for col in range(14):
            saved_width = self.settings.value(f'catalog_tree_col_{col}')
            if saved_width:
                self.catalog_tree.setColumnWidth(col, int(saved_width))
            else:
                self.catalog_tree.setColumnWidth(col, default_widths[col])

        # Restore column order
        saved_order = self.settings.value('catalog_tree_col_order')
        if saved_order:
            # Convert to integers (QSettings may return strings)
            saved_order = [int(idx) for idx in saved_order]
            for visual_index, logical_index in enumerate(saved_order):
                self.catalog_tree.header().moveSection(
                    self.catalog_tree.header().visualIndex(logical_index),
                    visual_index
                )

        # Connect signals to save settings
        self.catalog_tree.header().sectionResized.connect(self.save_catalog_tree_column_widths)
        self.catalog_tree.header().sectionMoved.connect(self.save_catalog_tree_column_order)

        # Enable multi-selection
        self.catalog_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

        # Enable context menu
        self.catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.catalog_tree.customContextMenuRequested.connect(self.show_catalog_context_menu)

        # Connect itemExpanded for lazy loading
        self.catalog_tree.itemExpanded.connect(self._on_tree_item_expanded)

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

        # Get all selected items
        selected_items = self.catalog_tree.selectedItems()

        menu = QMenu()

        # Check if multiple items are selected
        if len(selected_items) > 1:
            # Filter to only file items (no group nodes)
            file_items = [
                item for item in selected_items
                if item.childCount() == 0 and '(' not in item.text(0)
            ]

            # Filter to only light frame files for approval actions
            light_frames = [
                item for item in file_items
                if 'light' in item.text(1).lower()
            ]

            if file_items:
                # Show bulk approval actions only if there are light frames
                bulk_approve_action = None
                bulk_reject_action = None
                bulk_clear_action = None

                if light_frames:
                    bulk_approve_action = menu.addAction(f"✓ Approve {len(light_frames)} Frame(s)")
                    bulk_reject_action = menu.addAction(f"✗ Reject {len(light_frames)} Frame(s)")
                    bulk_clear_action = menu.addAction(f"○ Clear Grading for {len(light_frames)} Frame(s)")
                    menu.addSeparator()

                # Add bulk delete submenu for all file types
                bulk_delete_menu = menu.addMenu(f"Delete {len(file_items)} File(s)...")
                bulk_delete_db_only_action = bulk_delete_menu.addAction("From Database Only")
                bulk_delete_disk_only_action = bulk_delete_menu.addAction("From Disk Only")
                bulk_delete_both_action = bulk_delete_menu.addAction("From Database and Disk")

                action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

                if action is None:
                    return

                if light_frames and action == bulk_approve_action:
                    self.bulk_approve_frames(light_frames)
                elif light_frames and action == bulk_reject_action:
                    self.bulk_reject_frames(light_frames)
                elif light_frames and action == bulk_clear_action:
                    self.bulk_clear_grading(light_frames)
                elif action == bulk_delete_db_only_action:
                    self.delete_files_with_options(file_items, delete_from_db=True, delete_from_disk=False)
                elif action == bulk_delete_disk_only_action:
                    self.delete_files_with_options(file_items, delete_from_db=False, delete_from_disk=True)
                elif action == bulk_delete_both_action:
                    self.delete_files_with_options(file_items, delete_from_db=True, delete_from_disk=True)
                return

        # Single item context menu
        # Only show file operations if this is a file item (has no children and is not a group node)
        is_file = item.childCount() == 0 and '(' not in item.text(0)

        # Check if this is a date node (session) - has children and date_loc in column 6
        is_session = item.childCount() > 0 and item.text(6) and '(' in item.text(0)

        if is_file:
            # Approval actions (only for light frames)
            imagetyp = item.text(1)

            # Initialize approval action variables
            approve_action = None
            reject_action = None
            clear_grading_action = None

            if 'light' in imagetyp.lower():
                approve_action = menu.addAction("✓ Approve Frame")
                reject_action = menu.addAction("✗ Reject Frame")
                clear_grading_action = menu.addAction("○ Clear Grading")
                menu.addSeparator()

            show_path_action = menu.addAction("Show Full Path")
            copy_path_action = menu.addAction("Copy Path to Clipboard")
            open_location_action = menu.addAction("Open File Location")
            menu.addSeparator()
            show_details_action = menu.addAction("Show File Details")
            menu.addSeparator()

            # Delete submenu with options
            delete_menu = menu.addMenu("Delete File...")
            delete_db_only_action = delete_menu.addAction("From Database Only")
            delete_disk_only_action = delete_menu.addAction("From Disk Only")
            delete_both_action = delete_menu.addAction("From Database and Disk")

            menu.addSeparator()
            reimport_action = menu.addAction("Re-import File")

            action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

            # Check if user cancelled the menu
            if action is None:
                return

            # Handle approval actions
            if 'light' in imagetyp.lower():
                if action == approve_action:
                    self.approve_frame(item)
                    return
                elif action == reject_action:
                    self.reject_frame(item)
                    return
                elif action == clear_grading_action:
                    self.clear_frame_grading(item)
                    return

            if action == show_path_action:
                self.show_file_path(item)
            elif action == copy_path_action:
                self.copy_file_path_to_clipboard(item)
            elif action == open_location_action:
                self.open_file_location(item)
            elif action == show_details_action:
                self.show_file_details(item)
            elif action == delete_db_only_action:
                self.delete_files_with_options([item], delete_from_db=True, delete_from_disk=False)
            elif action == delete_disk_only_action:
                self.delete_files_with_options([item], delete_from_db=False, delete_from_disk=True)
            elif action == delete_both_action:
                self.delete_files_with_options([item], delete_from_db=True, delete_from_disk=True)
            elif action == reimport_action:
                self.reimport_file(item)
        elif is_session:
            # Session node - check if already assigned to a project
            date_loc = item.text(6)
            parent = item.parent()
            if parent:
                parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
                if parent_data:
                    object_name = parent_data.get('object')
                    filter_name = parent_data.get('filter')

                    # Check if session is assigned
                    assignment = self.project_manager.get_session_assignment(
                        date_loc, object_name, filter_name
                    )

                    if assignment:
                        # Session is assigned - show unassign option
                        project_id, assignment_id, project_name = assignment
                        unassign_action = menu.addAction(f"Unassign from Project '{project_name}'")
                        menu.addSeparator()
                        export_action = menu.addAction("Export This Group to CSV")

                        action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

                        if action == unassign_action:
                            self.unassign_session_from_project(item, project_name)
                        elif action == export_action:
                            self.export_tree_group_to_csv(item)
                    else:
                        # Session not assigned - show assign option
                        assign_action = menu.addAction("Assign to Project")
                        menu.addSeparator()
                        export_action = menu.addAction("Export This Group to CSV")

                        action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

                        if action == assign_action:
                            self.assign_session_to_project(item)
                        elif action == export_action:
                            self.export_tree_group_to_csv(item)
                else:
                    # Fallback if parent_data not available
                    export_action = menu.addAction("Export This Group to CSV")
                    action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

                    if action == export_action:
                        self.export_tree_group_to_csv(item)
            else:
                # Fallback if parent not available
                export_action = menu.addAction("Export This Group to CSV")
                action = menu.exec(self.catalog_tree.viewport().mapToGlobal(position))

                if action == export_action:
                    self.export_tree_group_to_csv(item)
        else:
            # For other group nodes, offer export
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

    def delete_files_with_options(self, items: list, delete_from_db: bool = True, delete_from_disk: bool = False) -> None:
        """
        Delete files from the database and/or disk.

        Args:
            items: List of QTreeWidgetItem objects representing files
            delete_from_db: Whether to delete from database
            delete_from_disk: Whether to delete from disk
        """
        if not items:
            return

        # Get filenames and file paths
        file_info = []
        for item in items:
            filename = item.text(0)
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    file_info.append({'filename': filename, 'filepath': result[0]})
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to retrieve file info for {filename}: {e}')
                return

        if not file_info:
            QMessageBox.warning(self, 'No Files', 'No files found in database.')
            return

        # Build confirmation message
        count = len(file_info)
        if count == 1:
            message = f'Are you sure you want to delete "{file_info[0]["filename"]}"'
        else:
            message = f'Are you sure you want to delete {count} files'

        actions = []
        if delete_from_db and delete_from_disk:
            actions.append('from the database AND from disk')
        elif delete_from_db:
            actions.append('from the database')
        elif delete_from_disk:
            actions.append('from disk')

        message += ' ' + ', '.join(actions) + '?'

        # Add warning based on deletion type
        if delete_from_disk:
            message += '\n\n⚠️ WARNING: Files deleted from disk cannot be recovered!'

        reply = QMessageBox.question(
            self, 'Confirm Delete',
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success_count = 0
            failed_files = []

            for info in file_info:
                filename = info['filename']
                filepath = info['filepath']
                file_success = True

                # Delete from database
                if delete_from_db:
                    try:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM xisf_files WHERE filename = ?', (filename,))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        failed_files.append(f'{filename}: DB deletion failed - {e}')
                        file_success = False

                # Delete from disk
                if delete_from_disk and file_success:
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        else:
                            failed_files.append(f'{filename}: File not found on disk')
                            file_success = False
                    except Exception as e:
                        failed_files.append(f'{filename}: Disk deletion failed - {e}')
                        file_success = False

                if file_success:
                    success_count += 1

            # Show results
            if success_count > 0:
                self.refresh_catalog_view()

            if failed_files:
                error_msg = f'Successfully deleted {success_count} of {count} file(s).\n\nFailed:\n' + '\n'.join(failed_files)
                QMessageBox.warning(self, 'Partial Success', error_msg)
            else:
                if count == 1:
                    QMessageBox.information(self, 'Success', f'File deleted successfully: {file_info[0]["filename"]}')
                else:
                    QMessageBox.information(self, 'Success', f'{count} files deleted successfully')

    def delete_file_from_database(self, item: QTreeWidgetItem) -> None:
        """
        Delete a file from the database (legacy method - kept for backwards compatibility).

        This method is deprecated. Use delete_files_with_options instead.
        """
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

    def assign_session_to_project(self, item: QTreeWidgetItem) -> None:
        """
        Assign a session (date node) to a project.

        Args:
            item: Date node tree item
        """
        try:
            # Get date_loc from column 6
            date_loc = item.text(6)
            if not date_loc:
                QMessageBox.warning(self, 'Error', 'Could not determine session date')
                return

            # Get parent filter node to extract object and filter
            parent = item.parent()
            if not parent:
                QMessageBox.warning(self, 'Error', 'Could not determine session details')
                return

            # Get object and filter from parent node's data
            parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
            if not parent_data:
                QMessageBox.warning(self, 'Error', 'Could not determine session details')
                return

            object_name = parent_data.get('object')
            filter_name = parent_data.get('filter')

            if not object_name:
                QMessageBox.warning(self, 'Error', 'Could not determine object name')
                return

            # Count frames in this session
            frame_count = item.childCount()

            # Open assign session dialog
            dialog = AssignSessionDialog(
                db_path=self.db_path,
                date_loc=date_loc,
                object_name=object_name,
                filter_name=filter_name,
                frame_count=frame_count,
                parent=self
            )

            if dialog.exec() == dialog.DialogCode.Accepted:
                self.status_callback(f'Session assigned to project')
                # Optionally refresh the view to show assignment status
                # self.refresh_catalog_view()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to assign session: {e}')

    def unassign_session_from_project(self, item: QTreeWidgetItem, project_name: str) -> None:
        """
        Unassign a session (date node) from a project.

        Args:
            item: Date node tree item
            project_name: Name of the project (for confirmation message)
        """
        try:
            # Get date_loc from column 6
            date_loc = item.text(6)
            if not date_loc:
                QMessageBox.warning(self, 'Error', 'Could not determine session date')
                return

            # Get parent filter node to extract object and filter
            parent = item.parent()
            if not parent:
                QMessageBox.warning(self, 'Error', 'Could not determine session details')
                return

            # Get object and filter from parent node's data
            parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
            if not parent_data:
                QMessageBox.warning(self, 'Error', 'Could not determine session details')
                return

            object_name = parent_data.get('object')
            filter_name = parent_data.get('filter')

            if not object_name:
                QMessageBox.warning(self, 'Error', 'Could not determine object name')
                return

            # Confirm unassignment
            frame_count = item.childCount()
            filter_str = f" ({filter_name})" if filter_name else ""
            reply = QMessageBox.question(
                self,
                'Confirm Unassignment',
                f"Unassign this session from project '{project_name}'?\n\n"
                f"Session: {date_loc}\n"
                f"Object: {object_name}{filter_str}\n"
                f"Frames: {frame_count}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Unassign the session
                self.project_manager.unassign_session_from_project(
                    date_loc=date_loc,
                    object_name=object_name,
                    filter_name=filter_name
                )

                self.status_callback(f'Session unassigned from project \'{project_name}\'')
                QMessageBox.information(
                    self,
                    'Success',
                    f'Session unassigned from project \'{project_name}\''
                )

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to unassign session: {e}')

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
        """Refresh the catalog view using background thread (non-blocking)."""
        try:
            # Cancel any existing worker
            if self.loader_worker:
                if self.loader_worker.isRunning():
                    self.loader_worker.terminate()
                    self.loader_worker.wait()

                # Disconnect all signals from old worker to prevent stale data
                try:
                    self.loader_worker.progress_updated.disconnect()
                    self.loader_worker.data_ready.disconnect()
                    self.loader_worker.error_occurred.disconnect()
                    self.loader_worker.finished.disconnect()
                except TypeError:
                    # Signals were not connected or already disconnected
                    pass

                # Clean up old worker
                self.loader_worker.deleteLater()
                self.loader_worker = None

            # Update statistics synchronously (fast operation)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            self.update_catalog_statistics(cursor)
            conn.close()

            # Show progress
            self.catalog_progress_widget.show()
            self.catalog_status_label.setText("Loading catalog...")
            self.catalog_tree.setEnabled(False)

            # Get filter values
            imagetype_filter = self.catalog_imagetype_filter.currentText()
            object_filter = self.catalog_object_filter.currentText()
            approval_filter = self.catalog_approval_filter.currentText()

            # Create and start worker
            self.loader_worker = CatalogLoaderWorker(self.db_path, imagetype_filter, object_filter, approval_filter)
            self.loader_worker.progress_updated.connect(self._on_catalog_progress)
            self.loader_worker.data_ready.connect(self._on_catalog_data_ready)
            self.loader_worker.error_occurred.connect(self._on_catalog_error)
            self.loader_worker.finished.connect(self._on_catalog_finished)
            self.loader_worker.start()

        except Exception as e:
            self.catalog_progress_widget.hide()
            self.catalog_tree.setEnabled(True)
            QMessageBox.critical(self, 'Error', f'Failed to start catalog load: {e}')

    def _on_catalog_progress(self, message: str) -> None:
        """Update progress message."""
        self.catalog_status_label.setText(message)

    def _on_catalog_error(self, error_msg: str) -> None:
        """Handle worker error."""
        self.catalog_progress_widget.hide()
        self.catalog_tree.setEnabled(True)
        QMessageBox.critical(self, 'Error', error_msg)

    def _on_catalog_finished(self) -> None:
        """Hide progress when worker finishes."""
        self.catalog_progress_widget.hide()
        self.catalog_tree.setEnabled(True)

    def _on_catalog_data_ready(self, result: dict) -> None:
        """
        Build catalog tree from loaded data (runs on UI thread).

        Args:
            result: Dictionary with 'objects', 'light_data', 'calib_data' keys
        """
        try:
            # Update object filter dropdown
            objects = result.get('objects', [])
            current_object = self.catalog_object_filter.currentText()

            self.catalog_object_filter.blockSignals(True)
            self.catalog_object_filter.clear()
            self.catalog_object_filter.addItem('All')
            self.catalog_object_filter.addItems(objects)

            if current_object in ['All'] + objects:
                self.catalog_object_filter.setCurrentText(current_object)

            self.catalog_object_filter.blockSignals(False)

            # Save expanded state before clearing
            expanded_paths = self._save_expanded_state()

            # Clear and build tree
            self.catalog_tree.setUpdatesEnabled(False)
            self.catalog_tree.clear()

            # Build light frames tree from data
            light_data = result.get('light_data', [])
            if light_data:
                self._build_light_frames_from_data(light_data)

            # Build calibration frames tree from data
            calib_data = result.get('calib_data', {})
            if any(calib_data.values()):  # If any calibration data exists
                self._build_calibration_frames_from_data(calib_data)

            # Restore expanded state
            self._restore_expanded_state(expanded_paths)

            self.catalog_tree.setUpdatesEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to build tree: {e}')

    def _build_light_frames_from_data(self, light_data: list) -> None:
        """Build light frames tree with lazy loading (only objects and filters initially)."""
        if not light_data:
            return

        # Store data for lazy loading
        self.light_data_cache = light_data

        # Calculate totals
        total_count = len(light_data)
        total_exp = sum(row[5] or 0 for row in light_data) / 3600.0  # exposure is column 5

        light_frames_root = QTreeWidgetItem(self.catalog_tree)
        light_frames_root.setText(0, f"Light Frames ({total_count} files, {total_exp:.1f}h)")
        light_frames_root.setFlags(light_frames_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
        font = light_frames_root.font(0)
        font.setBold(True)
        light_frames_root.setFont(0, font)

        # LAZY LOADING: Only build objects → filters (2 levels)
        # Dates and files will be loaded on-demand when filter nodes are expanded

        # Track current state
        current_obj = None
        obj_item = None

        # Aggregation tracking
        obj_files = {}
        filter_files = {}

        # Aggregate counts
        for row in light_data:
            obj, filt = row[0], row[1]
            exposure = row[5] or 0

            if obj not in obj_files:
                obj_files[obj] = {'count': 0, 'exposure': 0}
            obj_files[obj]['count'] += 1
            obj_files[obj]['exposure'] += exposure

            key_filter = (obj, filt)
            if key_filter not in filter_files:
                filter_files[key_filter] = {'count': 0, 'exposure': 0}
            filter_files[key_filter]['count'] += 1
            filter_files[key_filter]['exposure'] += exposure

        # Build only objects and filters
        for row in light_data:
            obj, filt = row[0], row[1]

            # Create object node if new
            if obj != current_obj:
                obj_stats = obj_files[obj]
                obj_exp_hrs = obj_stats['exposure'] / 3600.0
                obj_item = QTreeWidgetItem(light_frames_root)
                obj_item.setText(0, f"{obj or 'Unknown'} ({obj_stats['count']} files, {obj_exp_hrs:.1f}h)")
                obj_item.setFlags(obj_item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
                current_obj = obj

            # Check if filter node already exists for this object
            filter_exists = False
            for i in range(obj_item.childCount()):
                child = obj_item.child(i)
                stored_filter = child.data(0, Qt.ItemDataRole.UserRole)
                if stored_filter and stored_filter.get('filter') == filt:
                    filter_exists = True
                    break

            if not filter_exists:
                filter_stats = filter_files[(obj, filt)]
                filter_exp_hrs = filter_stats['exposure'] / 3600.0
                filter_item = QTreeWidgetItem(obj_item)
                filter_item.setText(0, f"{filt or 'No Filter'} ({filter_stats['count']} files, {filter_exp_hrs:.1f}h)")
                filter_item.setText(2, filt or 'No Filter')

                # Store metadata for lazy loading
                filter_item.setData(0, Qt.ItemDataRole.UserRole, {
                    'object': obj,
                    'filter': filt,
                    'lazy_load': True  # Mark for lazy loading
                })

                # Add a dummy child to make it expandable
                dummy = QTreeWidgetItem(filter_item)
                dummy.setText(0, "Loading...")
                dummy.setData(0, Qt.ItemDataRole.UserRole, {'dummy': True})

    def _on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Handle tree item expansion for lazy loading."""
        # Check if this item needs lazy loading
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data or not item_data.get('lazy_load'):
            return

        # Check if already loaded (no dummy children)
        if item.childCount() > 0:
            first_child = item.child(0)
            first_child_data = first_child.data(0, Qt.ItemDataRole.UserRole)
            if not first_child_data or not first_child_data.get('dummy'):
                return  # Already loaded

        # Get the object and filter for this node
        obj = item_data.get('object')
        filt = item_data.get('filter')

        # Filter the cached data for this object/filter combination
        filtered_data = [
            row for row in self.light_data_cache
            if row[0] == obj and row[1] == filt
        ]

        if not filtered_data:
            # Remove dummy and mark as loaded
            item.takeChildren()
            return

        # Aggregate by date
        date_files = {}
        for row in filtered_data:
            date_loc = row[2]
            exposure = row[5] or 0

            if date_loc not in date_files:
                date_files[date_loc] = {'count': 0, 'exposure': 0, 'rows': []}
            date_files[date_loc]['count'] += 1
            date_files[date_loc]['exposure'] += exposure
            date_files[date_loc]['rows'].append(row)

        # Remove dummy children
        item.takeChildren()

        # Build date nodes and file nodes
        for date_loc in sorted(date_files.keys(), reverse=True):  # Most recent first
            date_stats = date_files[date_loc]
            date_exp_hrs = date_stats['exposure'] / 3600.0
            date_item = QTreeWidgetItem(item)
            date_item.setText(0, f"{date_loc or 'No Date'} ({date_stats['count']} files, {date_exp_hrs:.1f}h)")
            date_item.setText(6, date_loc or 'No Date')

            # Add file nodes for this date
            for row in sorted(date_stats['rows'], key=lambda x: x[3]):  # Sort by filename
                obj, filt, date_loc, filename, imagetyp, exposure, temp, xbin, ybin, telescop, instrume, fwhm, eccentricity, snr, star_count, approval_status = row

                file_item = QTreeWidgetItem(date_item)
                file_item.setText(0, filename)
                file_item.setText(1, imagetyp or 'N/A')
                file_item.setText(2, filt or 'N/A')
                file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
                file_item.setText(4, f"{temp:.1f}°C" if temp is not None else 'N/A')
                binning = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
                file_item.setText(5, binning)
                file_item.setText(6, date_loc or 'N/A')

                # Quality metrics columns
                file_item.setText(7, f"{fwhm:.2f}" if fwhm is not None else '')
                file_item.setText(8, f"{eccentricity:.2f}" if eccentricity is not None else '')
                file_item.setText(9, f"{snr:.1f}" if snr is not None else '')
                file_item.setText(10, f"{star_count}" if star_count is not None else '')

                # Approval status with icon
                if approval_status == 'approved':
                    file_item.setText(11, '✓ Approved')
                elif approval_status == 'rejected':
                    file_item.setText(11, '✗ Rejected')
                else:
                    file_item.setText(11, '○ Not Graded')

                file_item.setText(12, telescop or 'N/A')
                file_item.setText(13, instrume or 'N/A')

                # Apply color coding based on approval status
                approval_color = None
                if approval_status == 'approved':
                    approval_color = QColor(200, 255, 200)  # Light green
                elif approval_status == 'rejected':
                    approval_color = QColor(255, 200, 200)  # Light red

                if approval_color:
                    for col in range(14):
                        file_item.setBackground(col, QBrush(approval_color))
                else:
                    # Apply imagetyp color coding for non-graded frames
                    color = self.get_item_color(imagetyp)
                    if color:
                        for col in range(14):
                            file_item.setBackground(col, QBrush(color))

        # Mark as loaded by removing lazy_load flag
        item_data['lazy_load'] = False
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)


    def _build_calibration_frames_from_data(self, calib_data: dict) -> None:
        """Build calibration frames tree from pre-loaded data."""
        darks = calib_data.get('darks', [])
        flats = calib_data.get('flats', [])
        bias = calib_data.get('bias', [])

        total_count = len(darks) + len(flats) + len(bias)
        if total_count == 0:
            return

        calib_root = QTreeWidgetItem(self.catalog_tree)
        calib_root.setText(0, f"Calibration Frames ({total_count} files)")
        calib_root.setFlags(calib_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
        font = calib_root.font(0)
        font.setBold(True)
        calib_root.setFont(0, font)

        # Build darks
        if darks:
            self._build_darks_from_data(calib_root, darks)

        # Build flats
        if flats:
            self._build_flats_from_data(calib_root, flats)

        # Build bias
        if bias:
            self._build_bias_from_data(calib_root, bias)
    
    
    def _build_darks_from_data(self, calib_root, darks_data: list) -> None:
        """Build darks tree from pre-loaded data."""
        dark_root = QTreeWidgetItem(calib_root)
        dark_root.setText(0, f"Dark Frames ({len(darks_data)} files)")
        dark_root.setFlags(dark_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

        current_group = None
        current_date = None
        group_item = None
        date_item = None

        for row in darks_data:
            exp, temp, xbin, ybin, date_loc, filename, imagetyp, telescop, instrume, actual_temp = row

            # Create group node if new
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
    
    
    def _build_flats_from_data(self, calib_root, flats_data: list) -> None:
        """Build flats tree from pre-loaded data."""
        flat_root = QTreeWidgetItem(calib_root)
        flat_root.setText(0, f"Flat Frames ({len(flats_data)} files)")
        flat_root.setFlags(flat_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

        current_date = None
        current_group = None
        date_item = None
        group_item = None

        for row in flats_data:
            date_loc, filt, temp, xbin, ybin, filename, imagetyp, exposure, telescop, instrume, actual_temp = row

            # Create date node if new
            if date_loc != current_date:
                date_item = QTreeWidgetItem(flat_root)
                date_item.setText(0, date_loc or 'No Date')
                current_date = date_loc
                current_group = None

            # Create group node if new
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
    
    
    def _build_bias_from_data(self, calib_root, bias_data: list) -> None:
        """Build bias tree from pre-loaded data."""
        bias_root = QTreeWidgetItem(calib_root)
        bias_root.setText(0, f"Bias Frames ({len(bias_data)} files)")
        bias_root.setFlags(bias_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

        current_group = None
        current_date = None
        group_item = None
        date_item = None

        for row in bias_data:
            temp, xbin, ybin, date_loc, filename, imagetyp, exposure, telescop, instrume, actual_temp, filt = row

            # Create group node if new
            group_key = (temp, xbin, ybin)
            if group_key != current_group:
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"

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

    def _save_expanded_state(self) -> set:
        """
        Save the expanded state of all tree items.

        Returns:
            Set of tuples representing paths to expanded items
        """
        expanded_paths = set()

        def save_item_state(item: QTreeWidgetItem, path: tuple = ()):
            """Recursively save expanded state."""
            # Create path using item text from column 0
            current_path = path + (item.text(0),)

            # If item is expanded, save its path
            if item.isExpanded():
                expanded_paths.add(current_path)

            # Process children
            for i in range(item.childCount()):
                save_item_state(item.child(i), current_path)

        # Process all top-level items
        root = self.catalog_tree.invisibleRootItem()
        for i in range(root.childCount()):
            save_item_state(root.child(i))

        return expanded_paths

    def _restore_expanded_state(self, expanded_paths: set):
        """
        Restore the expanded state of tree items.

        Args:
            expanded_paths: Set of tuples representing paths to expanded items
        """
        if not expanded_paths:
            return

        def restore_item_state(item: QTreeWidgetItem, path: tuple = ()):
            """Recursively restore expanded state."""
            # Create path using item text from column 0
            current_path = path + (item.text(0),)

            # If this path was expanded, expand it
            if current_path in expanded_paths:
                item.setExpanded(True)

            # Process children
            for i in range(item.childCount()):
                restore_item_state(item.child(i), current_path)

        # Process all top-level items
        root = self.catalog_tree.invisibleRootItem()
        for i in range(root.childCount()):
            restore_item_state(root.child(i))

    def approve_frame(self, item: QTreeWidgetItem) -> None:
        """Mark a frame as approved."""
        self._update_approval_status(item, 'approved')

    def reject_frame(self, item: QTreeWidgetItem) -> None:
        """Mark a frame as rejected."""
        self._update_approval_status(item, 'rejected')

    def clear_frame_grading(self, item: QTreeWidgetItem) -> None:
        """Clear the grading status of a frame."""
        self._update_approval_status(item, 'not_graded')

    def bulk_approve_frames(self, items: list) -> None:
        """Mark multiple frames as approved."""
        self._bulk_update_approval_status(items, 'approved')

    def bulk_reject_frames(self, items: list) -> None:
        """Mark multiple frames as rejected."""
        self._bulk_update_approval_status(items, 'rejected')

    def bulk_clear_grading(self, items: list) -> None:
        """Clear grading status for multiple frames."""
        self._bulk_update_approval_status(items, 'not_graded')

    def _bulk_update_approval_status(self, items: list, status: str) -> None:
        """
        Update approval status for multiple frames in bulk.

        Args:
            items: List of QTreeWidgetItem objects representing files
            status: New approval status ('approved', 'rejected', or 'not_graded')
        """
        from datetime import datetime

        if not items:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            grading_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status != 'not_graded' else None

            # Get filenames from items
            filenames = [item.text(0) for item in items]

            # Get project_ids for affected frames before update
            placeholders = ','.join(['?'] * len(filenames))
            cursor.execute(f'''
                SELECT DISTINCT project_id
                FROM xisf_files
                WHERE filename IN ({placeholders})
                AND project_id IS NOT NULL
            ''', filenames)
            project_ids = [row[0] for row in cursor.fetchall()]

            # Build bulk update query
            cursor.execute(f'''
                UPDATE xisf_files
                SET approval_status = ?, grading_date = ?
                WHERE filename IN ({placeholders})
            ''', [status, grading_date] + filenames)

            conn.commit()
            conn.close()

            # Recalculate project counts for all affected projects
            for project_id in project_ids:
                self.project_manager.recalculate_project_counts(project_id)

            # Update visual display for all items
            if status == 'approved':
                status_text = '✓ Approved'
                color = QColor(200, 255, 200)  # Light green
            elif status == 'rejected':
                status_text = '✗ Rejected'
                color = QColor(255, 200, 200)  # Light red
            else:
                status_text = '○ Not Graded'
                color = None

            for item in items:
                item.setText(11, status_text)
                if color:
                    for col in range(14):
                        item.setBackground(col, QBrush(color))
                else:
                    # Clear background
                    for col in range(14):
                        item.setBackground(col, QBrush())

            self.status_callback(f"{len(items)} frame(s) marked as {status}")

            # If an approval filter is active, refresh the view to apply the filter
            if hasattr(self, 'catalog_approval_filter') and self.catalog_approval_filter.currentText() != 'All':
                self.refresh_catalog_view()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to update approval status: {e}')

    def _update_approval_status(self, item: QTreeWidgetItem, status: str) -> None:
        """
        Update the approval status of a frame in the database.

        Args:
            item: Tree widget item representing the file
            status: New approval status ('approved', 'rejected', or 'not_graded')
        """
        from datetime import datetime

        filename = item.text(0)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get project_id before update (if frame is assigned to a project)
            cursor.execute('SELECT project_id FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            project_id = result[0] if result and result[0] else None

            # Update approval status
            grading_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status != 'not_graded' else None

            cursor.execute('''
                UPDATE xisf_files
                SET approval_status = ?, grading_date = ?
                WHERE filename = ?
            ''', (status, grading_date, filename))

            conn.commit()
            conn.close()

            # Recalculate project counts if frame is part of a project
            if project_id:
                self.project_manager.recalculate_project_counts(project_id)

            # Update the item display
            if status == 'approved':
                item.setText(11, '✓ Approved')
                color = QColor(200, 255, 200)  # Light green
            elif status == 'rejected':
                item.setText(11, '✗ Rejected')
                color = QColor(255, 200, 200)  # Light red
            else:
                item.setText(11, '○ Not Graded')
                color = None

            # Update item color
            if color:
                for col in range(14):
                    item.setBackground(col, QBrush(color))
            else:
                # Clear background to show default
                for col in range(14):
                    item.setBackground(col, QBrush())

            self.status_callback(f"Frame {filename} marked as {status}")

            # If an approval filter is active, refresh the view to apply the filter
            if hasattr(self, 'catalog_approval_filter') and self.catalog_approval_filter.currentText() != 'All':
                self.refresh_catalog_view()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to update approval status: {e}')

    def save_catalog_tree_column_widths(self) -> None:
        """Save the catalog tree column widths to settings."""
        for col in range(self.catalog_tree.columnCount()):
            width = self.catalog_tree.columnWidth(col)
            self.settings.setValue(f'catalog_tree_col_{col}', width)

    def save_catalog_tree_column_order(self) -> None:
        """Save the catalog tree column order to settings."""
        header = self.catalog_tree.header()
        order = [header.logicalIndex(i) for i in range(header.count())]
        self.settings.setValue('catalog_tree_col_order', order)
