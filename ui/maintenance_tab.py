"""
Maintenance tab UI for AstroFileManager.

This module contains the MaintenanceTab class which handles database maintenance
operations including clearing data, search and replace, and file organization.
"""

import os
import sqlite3
import shutil
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
    QLabel, QTextEdit, QGroupBox, QComboBox, QLineEdit, QListWidget,
    QListWidgetItem, QDoubleSpinBox, QRadioButton, QButtonGroup, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor

from utils.file_organizer import generate_organized_path


class MaintenanceTab(QWidget):
    """Maintenance tab for database and file management operations."""

    def __init__(self, db_path: str, settings: QSettings, import_log_widget: Optional[QTextEdit] = None) -> None:
        """
        Initialize Maintenance tab.

        Args:
            db_path: Path to SQLite database
            settings: QSettings instance for app settings
            import_log_widget: Optional reference to import tab's log widget
        """
        super().__init__()
        self.db_path = db_path
        self.settings = settings
        self.import_log_widget = import_log_widget
        self.clear_db_btn = None  # Will be set as reference

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Clear Database section
        clear_group = QGroupBox("Database Management")
        clear_layout = QVBoxLayout()

        clear_info = QLabel("Clear all records from the database:")
        clear_layout.addWidget(clear_info)

        self.clear_db_btn = QPushButton('Clear Database')
        self.clear_db_btn.clicked.connect(self.clear_database)
        self.clear_db_btn.setStyleSheet("QPushButton { background-color: #8b0000; color: white; } QPushButton:hover { background-color: #a00000; }")
        clear_layout.addWidget(self.clear_db_btn)

        clear_group.setLayout(clear_layout)
        layout.addWidget(clear_group)

        # Search and Replace section
        replace_group = QGroupBox("Search and Replace")
        replace_layout = QVBoxLayout()

        replace_info = QLabel("Replace values in FITS keywords:")
        replace_layout.addWidget(replace_info)

        # FITS Keyword selection
        keyword_layout = QHBoxLayout()
        keyword_label = QLabel("FITS Keyword:")
        keyword_label.setMinimumWidth(120)
        self.keyword_combo = QComboBox()
        self.keyword_combo.addItems([
            'TELESCOP', 'INSTRUME', 'OBJECT', 'FILTER',
            'IMAGETYP', 'DATE-LOC'
        ])
        self.keyword_combo.currentTextChanged.connect(self.on_keyword_changed)
        keyword_layout.addWidget(keyword_label)
        keyword_layout.addWidget(self.keyword_combo)
        replace_layout.addLayout(keyword_layout)

        # Current value selection
        current_value_layout = QHBoxLayout()
        current_value_label = QLabel("Current Value:")
        current_value_label.setMinimumWidth(120)
        self.current_value_combo = QComboBox()
        current_value_layout.addWidget(current_value_label)
        current_value_layout.addWidget(self.current_value_combo)
        replace_layout.addLayout(current_value_layout)

        # Replacement value input
        replacement_layout = QHBoxLayout()
        replacement_label = QLabel("Replacement Value:")
        replacement_label.setMinimumWidth(120)
        self.replacement_input = QLineEdit()
        replacement_layout.addWidget(replacement_label)
        replacement_layout.addWidget(self.replacement_input)
        replace_layout.addLayout(replacement_layout)

        # Replace button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.replace_btn = QPushButton('Replace Values')
        self.replace_btn.clicked.connect(self.replace_values)
        button_layout.addWidget(self.replace_btn)
        replace_layout.addLayout(button_layout)

        replace_group.setLayout(replace_layout)
        layout.addWidget(replace_group)

        # Master Frame Temperature Tagging section
        master_temp_group = QGroupBox("Master Frame Temperature Tagging")
        master_temp_layout = QVBoxLayout()

        master_temp_info = QLabel("Assign CCD-TEMP values to master calibration frames:")
        master_temp_layout.addWidget(master_temp_info)

        master_temp_help = QLabel("Master frames from PixInsight often lack CCD-TEMP metadata. Tag them here to enable session matching.")
        master_temp_help.setStyleSheet("color: #888888; font-size: 10px;")
        master_temp_layout.addWidget(master_temp_help)

        # Refresh button
        refresh_masters_btn = QPushButton('Refresh Master Frames List')
        refresh_masters_btn.clicked.connect(self.refresh_master_frames_list)
        master_temp_layout.addWidget(refresh_masters_btn)

        # List of master frames
        list_label = QLabel("Select master frames to tag:")
        master_temp_layout.addWidget(list_label)

        self.master_frames_list = QListWidget()
        self.master_frames_list.setMaximumHeight(150)
        self.master_frames_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        master_temp_layout.addWidget(self.master_frames_list)

        # Temperature input
        temp_input_layout = QHBoxLayout()
        temp_label = QLabel("CCD Temperature:")
        temp_label.setMinimumWidth(120)
        self.master_temp_spinbox = QDoubleSpinBox()
        self.master_temp_spinbox.setRange(-50.0, 50.0)
        self.master_temp_spinbox.setValue(-10.0)
        self.master_temp_spinbox.setSuffix(" °C")
        self.master_temp_spinbox.setDecimals(1)
        temp_input_layout.addWidget(temp_label)
        temp_input_layout.addWidget(self.master_temp_spinbox)
        temp_input_layout.addStretch()
        master_temp_layout.addLayout(temp_input_layout)

        # Tag button
        tag_button_layout = QHBoxLayout()
        tag_button_layout.addStretch()
        tag_masters_btn = QPushButton('Tag Selected Masters')
        tag_masters_btn.clicked.connect(self.tag_master_frames)
        tag_masters_btn.setStyleSheet("QPushButton { background-color: #2d7a2d; color: white; } QPushButton:hover { background-color: #3d8a3d; }")
        tag_button_layout.addWidget(tag_masters_btn)
        master_temp_layout.addLayout(tag_button_layout)

        master_temp_group.setLayout(master_temp_layout)
        layout.addWidget(master_temp_group)

        # Remove Duplicate Calibration Frames section
        remove_dupes_group = QGroupBox("Remove Duplicate Calibration Frames")
        remove_dupes_layout = QVBoxLayout()

        remove_dupes_info = QLabel("Identify and remove individual calibration frames when master frames exist:")
        remove_dupes_layout.addWidget(remove_dupes_info)

        remove_dupes_help = QLabel("When a master flat, dark, or bias frame exists, individual frames with matching parameters are redundant.")
        remove_dupes_help.setStyleSheet("color: #888888; font-size: 10px;")
        remove_dupes_layout.addWidget(remove_dupes_help)

        # Scan button
        scan_dupes_btn = QPushButton('Scan for Duplicates')
        scan_dupes_btn.clicked.connect(self.scan_for_duplicates)
        remove_dupes_layout.addWidget(scan_dupes_btn)

        # Results display
        self.dupes_results_label = QLabel("No scan performed yet")
        self.dupes_results_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 3px;")
        self.dupes_results_label.setWordWrap(True)
        remove_dupes_layout.addWidget(self.dupes_results_label)

        # Preview button
        self.preview_dupes_btn = QPushButton('Preview Duplicate List')
        self.preview_dupes_btn.clicked.connect(self.preview_duplicates)
        self.preview_dupes_btn.setEnabled(False)
        remove_dupes_layout.addWidget(self.preview_dupes_btn)

        # Removal options
        options_label = QLabel("Removal action:")
        remove_dupes_layout.addWidget(options_label)

        self.removal_button_group = QButtonGroup()

        self.remove_db_only_radio = QRadioButton("Remove from database only (keep files on disk)")
        self.remove_db_only_radio.setChecked(True)
        self.removal_button_group.addButton(self.remove_db_only_radio)
        remove_dupes_layout.addWidget(self.remove_db_only_radio)

        self.remove_db_and_files_radio = QRadioButton("Remove from database AND delete files from disk")
        self.removal_button_group.addButton(self.remove_db_and_files_radio)
        remove_dupes_layout.addWidget(self.remove_db_and_files_radio)

        # Remove button
        remove_dupes_button_layout = QHBoxLayout()
        remove_dupes_button_layout.addStretch()
        self.remove_dupes_btn = QPushButton('Remove Duplicates')
        self.remove_dupes_btn.clicked.connect(self.remove_duplicates)
        self.remove_dupes_btn.setEnabled(False)
        self.remove_dupes_btn.setStyleSheet("QPushButton { background-color: #8b0000; color: white; } QPushButton:hover { background-color: #a00000; }")
        remove_dupes_button_layout.addWidget(self.remove_dupes_btn)
        remove_dupes_layout.addLayout(remove_dupes_button_layout)

        remove_dupes_group.setLayout(remove_dupes_layout)
        layout.addWidget(remove_dupes_group)

        # File Organization section
        organize_group = QGroupBox("File Organization")
        organize_layout = QVBoxLayout()

        organize_info = QLabel("Organize files into standard folder structure with naming conventions:")
        organize_layout.addWidget(organize_info)

        # Preview button
        preview_btn = QPushButton('Preview Organization Plan')
        preview_btn.clicked.connect(self.preview_organization)
        organize_layout.addWidget(preview_btn)

        # Execute button
        execute_btn = QPushButton('Execute File Organization')
        execute_btn.clicked.connect(self.execute_organization)
        execute_btn.setStyleSheet("QPushButton { background-color: #2d7a2d; color: white; } QPushButton:hover { background-color: #3d8a3d; }")
        organize_layout.addWidget(execute_btn)

        # Organization log
        log_label = QLabel("Organization Log:")
        organize_layout.addWidget(log_label)

        self.organize_log = QTextEdit()
        self.organize_log.setReadOnly(True)
        self.organize_log.setMaximumHeight(200)
        organize_layout.addWidget(self.organize_log)

        organize_group.setLayout(organize_layout)
        layout.addWidget(organize_group)

        # Add stretch to push everything to the top
        layout.addStretch()

        # Populate initial values
        self.on_keyword_changed()

    def on_keyword_changed(self) -> None:
        """Update the current value dropdown when keyword selection changes."""
        keyword = self.keyword_combo.currentText()
        self.populate_current_values(keyword)

    def populate_current_values(self, keyword: str) -> None:
        """Populate the current value dropdown with existing values from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Map FITS keywords to database column names
            column_map = {
                'TELESCOP': 'telescop',
                'INSTRUME': 'instrume',
                'OBJECT': 'object',
                'FILTER': 'filter',
                'IMAGETYP': 'imagetyp',
                'DATE-LOC': 'date_loc'
            }

            column = column_map.get(keyword)
            if column:
                cursor.execute(f'SELECT DISTINCT {column} FROM xisf_files WHERE {column} IS NOT NULL ORDER BY {column}')
                values = [row[0] for row in cursor.fetchall()]

                self.current_value_combo.clear()
                self.current_value_combo.addItems(values)

            conn.close()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load values: {e}')

    def replace_values(self) -> None:
        """Replace values in the database and update filenames/folders for OBJECT and FILTER changes."""
        keyword = self.keyword_combo.currentText()
        current_value = self.current_value_combo.currentText()
        replacement_value = self.replacement_input.text()

        if not current_value:
            QMessageBox.warning(self, 'No Value Selected', 'Please select a current value to replace.')
            return

        if not replacement_value:
            QMessageBox.warning(self, 'No Replacement', 'Please enter a replacement value.')
            return

        # Confirm the replacement
        affects_organization = keyword in ['OBJECT', 'FILTER']
        confirmation_msg = (
            f'Replace all occurrences of:\n\n'
            f'Keyword: {keyword}\n'
            f'Current Value: "{current_value}"\n'
            f'Replacement Value: "{replacement_value}"\n\n'
        )

        if affects_organization:
            confirmation_msg += 'This will update the database, rename files, and move them to correct folders.\n\n'

        confirmation_msg += 'Are you sure?'

        reply = QMessageBox.question(
            self, 'Confirm Replacement',
            confirmation_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Map FITS keywords to database column names
                column_map = {
                    'TELESCOP': 'telescop',
                    'INSTRUME': 'instrume',
                    'OBJECT': 'object',
                    'FILTER': 'filter',
                    'IMAGETYP': 'imagetyp',
                    'DATE-LOC': 'date_loc'
                }

                column = column_map.get(keyword)
                if not column:
                    QMessageBox.critical(self, 'Error', f'Unknown keyword: {keyword}')
                    conn.close()
                    return

                # Get repository path if we need to reorganize files
                repo_path = None
                if affects_organization:
                    repo_path = self.settings.value('repository_path', '')
                    if not repo_path:
                        QMessageBox.warning(
                            self, 'No Repository Path',
                            'Repository path not set. Files will not be moved, only database will be updated.'
                        )

                updated_count = 0
                moved_count = 0
                errors = []

                # If this affects file organization, handle each file individually
                if affects_organization and repo_path:
                    # Get all affected files
                    cursor.execute(f'''
                        SELECT id, filepath, filename, object, filter, imagetyp,
                               exposure, ccd_temp, xbinning, ybinning, date_loc
                        FROM xisf_files
                        WHERE {column} = ?
                    ''', (current_value,))

                    affected_files = cursor.fetchall()

                    for row in affected_files:
                        file_id, old_filepath, old_filename, obj, filt, imgtyp, exp, temp, xbin, ybin, date_loc = row

                        # Update the appropriate field with new value
                        if keyword == 'OBJECT':
                            obj = replacement_value
                        elif keyword == 'FILTER':
                            filt = replacement_value

                        # Update database
                        cursor.execute(f'UPDATE xisf_files SET {column} = ? WHERE id = ?',
                                      (replacement_value, file_id))
                        updated_count += 1

                        # Move file if it exists
                        if old_filepath and os.path.exists(old_filepath):
                            try:
                                # Generate new organized path with updated value
                                new_filepath = generate_organized_path(
                                    repo_path, obj, filt, imgtyp, exp, temp,
                                    xbin, ybin, date_loc, old_filename
                                )

                                # Only move if the path is different
                                if old_filepath != new_filepath:
                                    # Create new directory if needed
                                    new_dir = os.path.dirname(new_filepath)
                                    os.makedirs(new_dir, exist_ok=True)

                                    # Move the file
                                    shutil.move(old_filepath, new_filepath)

                                    # Update database with new filepath and filename
                                    new_filename = os.path.basename(new_filepath)
                                    cursor.execute('''
                                        UPDATE xisf_files
                                        SET filepath = ?, filename = ?
                                        WHERE id = ?
                                    ''', (new_filepath, new_filename, file_id))

                                    moved_count += 1

                                    # Clean up old directory if empty
                                    old_dir = os.path.dirname(old_filepath)
                                    try:
                                        if old_dir and os.path.isdir(old_dir) and not os.listdir(old_dir):
                                            os.rmdir(old_dir)
                                            # Try to remove parent directory if also empty (for nested structures)
                                            parent_dir = os.path.dirname(old_dir)
                                            if parent_dir and os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                                                os.rmdir(parent_dir)
                                    except:
                                        pass  # Ignore cleanup errors

                            except Exception as e:
                                errors.append(f"{old_filename}: {str(e)}")

                else:
                    # Simple update for non-organization-affecting fields
                    cursor.execute(f'UPDATE xisf_files SET {column} = ? WHERE {column} = ?',
                                   (replacement_value, current_value))
                    updated_count = cursor.rowcount

                conn.commit()
                conn.close()

                # Show results
                message = f'Successfully replaced {updated_count} occurrence(s).'
                if moved_count > 0:
                    message += f'\n{moved_count} file(s) moved to new locations.'
                if errors:
                    message += f'\n\nErrors encountered:\n' + '\n'.join(errors[:5])
                    if len(errors) > 5:
                        message += f'\n... and {len(errors) - 5} more'

                if errors:
                    QMessageBox.warning(self, 'Completed with Errors', message)
                else:
                    QMessageBox.information(self, 'Success', message)

                # Refresh the current values dropdown
                self.populate_current_values(keyword)
                self.replacement_input.clear()

            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to replace values: {e}')

    def preview_organization(self) -> None:
        """Preview the file organization plan."""
        repo_path = self.settings.value('repository_path', '')

        if not repo_path:
            QMessageBox.warning(
                self, 'No Repository Path',
                'Please set the repository path in the Settings tab first.'
            )
            return

        self.organize_log.clear()
        self.organize_log.append("Generating organization preview...\n")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all files
            cursor.execute('''
                SELECT filepath, filename, object, filter, imagetyp,
                       exposure, ccd_temp, xbinning, ybinning, date_loc
                FROM xisf_files
                ORDER BY object, filter, date_loc
            ''')

            files = cursor.fetchall()
            conn.close()

            if not files:
                self.organize_log.append("No files found in database.")
                return

            self.organize_log.append(f"Found {len(files)} files to organize.\n")
            self.organize_log.append("Sample organization plan (showing first 10):\n")

            for i, (filepath, filename, obj, filt, imgtyp, exp, temp, xbin, ybin, date) in enumerate(files[:10]):
                new_path = generate_organized_path(
                    repo_path, obj, filt, imgtyp, exp, temp, xbin, ybin, date, filename
                )
                self.organize_log.append(f"\nFrom: {filepath}")
                self.organize_log.append(f"To:   {new_path}")

            if len(files) > 10:
                self.organize_log.append(f"\n... and {len(files) - 10} more files")

            self.organize_log.append("\n" + "="*60)
            self.organize_log.append("This is a preview only. No files have been moved.")

        except Exception as e:
            self.organize_log.append(f"\nError generating preview: {e}")

    def execute_organization(self) -> None:
        """Execute the file organization."""
        from utils.file_organizer import generate_organized_path

        repo_path = self.settings.value('repository_path', '')

        if not repo_path:
            QMessageBox.warning(
                self, 'No Repository Path',
                'Please set the repository path in the Settings tab first.'
            )
            return

        reply = QMessageBox.question(
            self, 'Confirm File Organization',
            'This will copy all files to the new organized structure and update the database.\n\n'
            'Original files will NOT be deleted.\n\n'
            'This may take some time. Continue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.organize_log.clear()
        self.organize_log.append("Starting file organization...\n")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all files
            cursor.execute('''
                SELECT id, filepath, filename, object, filter, imagetyp,
                       exposure, ccd_temp, xbinning, ybinning, date_loc
                FROM xisf_files
                ORDER BY object, filter, date_loc
            ''')

            files = cursor.fetchall()

            if not files:
                self.organize_log.append("No files found in database.")
                conn.close()
                return

            success_count = 0
            error_count = 0

            for file_id, filepath, filename, obj, filt, imgtyp, exp, temp, xbin, ybin, date in files:
                try:
                    # Check if source file exists
                    if not os.path.exists(filepath):
                        self.organize_log.append(f"❌ Source not found: {filepath}")
                        error_count += 1
                        continue

                    # Generate new path and filename
                    new_path = generate_organized_path(
                        repo_path, obj, filt, imgtyp, exp, temp, xbin, ybin, date, filename
                    )

                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)

                    # Copy file if it doesn't already exist at destination
                    if os.path.exists(new_path):
                        self.organize_log.append(f"⚠️  Already exists: {new_path}")
                    else:
                        shutil.copy2(filepath, new_path)
                        self.organize_log.append(f"✓ Copied: {os.path.basename(new_path)}")

                    # Update database with new path and filename
                    new_filename = os.path.basename(new_path)
                    cursor.execute('UPDATE xisf_files SET filepath = ?, filename = ? WHERE id = ?',
                                   (new_path, new_filename, file_id))
                    success_count += 1

                except Exception as e:
                    self.organize_log.append(f"❌ Error with {filename}: {e}")
                    error_count += 1

            conn.commit()
            conn.close()

            self.organize_log.append("\n" + "="*60)
            self.organize_log.append(f"Organization complete!")
            self.organize_log.append(f"Successfully organized: {success_count}")
            self.organize_log.append(f"Errors: {error_count}")

            QMessageBox.information(
                self, 'Organization Complete',
                f'Successfully organized {success_count} files.\n'
                f'Errors: {error_count}\n\n'
                'Check the log for details.'
            )

        except Exception as e:
            self.organize_log.append(f"\nFatal error: {e}")
            QMessageBox.critical(self, 'Error', f'Failed to organize files: {e}')

    def clear_database(self) -> None:
        """Clear all records from the database."""
        reply = QMessageBox.question(
            self, 'Confirm Clear',
            'Are you sure you want to delete all records from the database?\n\n'
            'This will clear:\n'
            '- All frame data\n'
            '- All projects\n'
            '- All project sessions\n'
            '- All project filter goals',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Delete from all tables
                # Order matters: delete child tables first to avoid foreign key issues
                cursor.execute('DELETE FROM project_sessions')
                cursor.execute('DELETE FROM project_filter_goals')
                cursor.execute('DELETE FROM projects')
                cursor.execute('DELETE FROM xisf_files')

                conn.commit()
                conn.close()

                # Log to import tab if available
                if self.import_log_widget:
                    self.import_log_widget.append('\nDatabase cleared successfully!')

                QMessageBox.information(self, 'Success', 'Database cleared successfully!')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to clear database: {e}')

    def refresh_master_frames_list(self) -> None:
        """Refresh the list of master calibration frames."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Query for all master frames, showing current temp status
            cursor.execute('''
                SELECT id, filename, imagetyp, ccd_temp, exposure, xbinning, ybinning
                FROM xisf_files
                WHERE imagetyp LIKE '%Master%'
                ORDER BY imagetyp, filename
            ''')

            master_frames = cursor.fetchall()
            conn.close()

            # Clear and populate the list
            self.master_frames_list.clear()

            if not master_frames:
                item = QListWidgetItem("No master frames found in database")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.master_frames_list.addItem(item)
                return

            for file_id, filename, imagetyp, ccd_temp, exposure, xbin, ybin in master_frames:
                # Format display text
                temp_str = f"{ccd_temp:.1f}°C" if ccd_temp is not None else "NO TEMP"
                exp_str = f"{exposure:.1f}s" if exposure is not None else "N/A"
                bin_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else "N/A"

                # Create display text
                display_text = f"{filename} [{imagetyp}] - {exp_str}, {temp_str}, Bin{bin_str}"

                # Create list item
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, file_id)  # Store database ID

                # Highlight items missing temperature
                if ccd_temp is None:
                    item.setForeground(QColor(255, 165, 0))  # Orange for missing temp

                self.master_frames_list.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load master frames: {e}')

    def tag_master_frames(self) -> None:
        """Apply temperature tag to selected master frames and update filenames/paths."""
        selected_items = self.master_frames_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, 'No Selection', 'Please select one or more master frames to tag.')
            return

        temperature = self.master_temp_spinbox.value()

        # Get file IDs from selected items
        file_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        # Confirm the operation
        reply = QMessageBox.question(
            self, 'Confirm Temperature Tagging',
            f'Set CCD-TEMP to {temperature}°C for {len(file_ids)} selected master frame(s)?\n\n'
            f'This will update the database, rename files, and move them to the correct folders.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get repository path from settings
            repo_path = self.settings.value('repository_path', '')
            if not repo_path:
                QMessageBox.warning(
                    self, 'No Repository Path',
                    'Repository path not set. Files will not be moved, only database will be updated.'
                )

            updated_count = 0
            moved_count = 0
            errors = []

            # Update temperature and move files for all selected frames
            for file_id in file_ids:
                # Get full file information
                cursor.execute('''
                    SELECT filepath, filename, object, filter, imagetyp,
                           exposure, xbinning, ybinning, date_loc
                    FROM xisf_files
                    WHERE id = ?
                ''', (file_id,))

                row = cursor.fetchone()
                if not row:
                    errors.append(f"File ID {file_id} not found")
                    continue

                old_filepath, old_filename, obj, filt, imgtyp, exp, xbin, ybin, date_loc = row

                # Update temperature in database
                cursor.execute('UPDATE xisf_files SET ccd_temp = ? WHERE id = ?',
                              (temperature, file_id))
                updated_count += 1

                # If repository path is set and file exists, move it
                if repo_path and old_filepath and os.path.exists(old_filepath):
                    try:
                        # Generate new organized path with updated temperature
                        new_filepath = generate_organized_path(
                            repo_path, obj, filt, imgtyp, exp, temperature,
                            xbin, ybin, date_loc, old_filename
                        )

                        # Only move if the path is different
                        if old_filepath != new_filepath:
                            # Create new directory if needed
                            new_dir = os.path.dirname(new_filepath)
                            os.makedirs(new_dir, exist_ok=True)

                            # Move the file
                            shutil.move(old_filepath, new_filepath)

                            # Update database with new filepath and filename
                            new_filename = os.path.basename(new_filepath)
                            cursor.execute('''
                                UPDATE xisf_files
                                SET filepath = ?, filename = ?
                                WHERE id = ?
                            ''', (new_filepath, new_filename, file_id))

                            moved_count += 1

                            # Clean up old directory if empty
                            old_dir = os.path.dirname(old_filepath)
                            try:
                                if old_dir and os.path.isdir(old_dir) and not os.listdir(old_dir):
                                    os.rmdir(old_dir)
                            except:
                                pass  # Ignore cleanup errors

                    except Exception as e:
                        errors.append(f"{old_filename}: {str(e)}")

            conn.commit()
            conn.close()

            # Show results
            message = f'Successfully updated {updated_count} master frame(s) with temperature {temperature}°C.'
            if moved_count > 0:
                message += f'\n{moved_count} file(s) moved to new locations.'
            if errors:
                message += f'\n\nErrors encountered:\n' + '\n'.join(errors[:5])
                if len(errors) > 5:
                    message += f'\n... and {len(errors) - 5} more'

            if errors:
                QMessageBox.warning(self, 'Completed with Errors', message)
            else:
                QMessageBox.information(self, 'Success', message)

            # Refresh the list to show updated temperatures
            self.refresh_master_frames_list()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to tag master frames: {e}')

    def scan_for_duplicates(self) -> None:
        """Scan for duplicate calibration frames where masters exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Store duplicate data for later use
            self.duplicate_data = {
                'darks': [],
                'flats': [],
                'bias': []
            }

            total_count = 0
            total_size = 0

            # Find duplicate dark frames
            cursor.execute('''
                SELECT DISTINCT
                    i.id, i.filepath, i.filename, i.exposure, i.ccd_temp, i.xbinning, i.ybinning
                FROM xisf_files i
                WHERE i.imagetyp LIKE '%Dark%'
                  AND i.imagetyp NOT LIKE '%Master%'
                  AND EXISTS (
                      SELECT 1 FROM xisf_files m
                      WHERE m.imagetyp LIKE '%Master%Dark%'
                        AND ABS(m.exposure - i.exposure) < 0.1
                        AND ABS(COALESCE(m.ccd_temp, 0) - COALESCE(i.ccd_temp, 0)) < 5
                        AND m.xbinning = i.xbinning
                        AND m.ybinning = i.ybinning
                  )
            ''')
            darks = cursor.fetchall()
            self.duplicate_data['darks'] = darks
            total_count += len(darks)

            # Find duplicate flat frames
            cursor.execute('''
                SELECT DISTINCT
                    i.id, i.filepath, i.filename, i.filter, i.date_loc, i.ccd_temp, i.xbinning, i.ybinning
                FROM xisf_files i
                WHERE i.imagetyp LIKE '%Flat%'
                  AND i.imagetyp NOT LIKE '%Master%'
                  AND EXISTS (
                      SELECT 1 FROM xisf_files m
                      WHERE m.imagetyp LIKE '%Master%Flat%'
                        AND (m.filter = i.filter OR (m.filter IS NULL AND i.filter IS NULL))
                        AND m.date_loc = i.date_loc
                        AND ABS(COALESCE(m.ccd_temp, 0) - COALESCE(i.ccd_temp, 0)) < 5
                        AND m.xbinning = i.xbinning
                        AND m.ybinning = i.ybinning
                  )
            ''')
            flats = cursor.fetchall()
            self.duplicate_data['flats'] = flats
            total_count += len(flats)

            # Find duplicate bias frames
            cursor.execute('''
                SELECT DISTINCT
                    i.id, i.filepath, i.filename, i.ccd_temp, i.xbinning, i.ybinning
                FROM xisf_files i
                WHERE i.imagetyp LIKE '%Bias%'
                  AND i.imagetyp NOT LIKE '%Master%'
                  AND EXISTS (
                      SELECT 1 FROM xisf_files m
                      WHERE m.imagetyp LIKE '%Master%Bias%'
                        AND ABS(COALESCE(m.ccd_temp, 0) - COALESCE(i.ccd_temp, 0)) < 5
                        AND m.xbinning = i.xbinning
                        AND m.ybinning = i.ybinning
                  )
            ''')
            bias = cursor.fetchall()
            self.duplicate_data['bias'] = bias
            total_count += len(bias)

            # Calculate total file size
            for frame_type in ['darks', 'flats', 'bias']:
                for row in self.duplicate_data[frame_type]:
                    filepath = row[1]  # filepath is second column
                    if filepath and os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            conn.close()

            # Format size
            size_str = self._format_file_size(total_size)

            # Update results label
            if total_count == 0:
                self.dupes_results_label.setText(
                    "No duplicate calibration frames found.\n"
                    "All individual frames have no corresponding master frames."
                )
                self.preview_dupes_btn.setEnabled(False)
                self.remove_dupes_btn.setEnabled(False)
            else:
                results_text = (
                    f"<b>Found {total_count} duplicate calibration frames:</b><br>"
                    f"• Dark frames: {len(darks)} files<br>"
                    f"• Flat frames: {len(flats)} files<br>"
                    f"• Bias frames: {len(bias)} files<br>"
                    f"<br><b>Total disk space: {size_str}</b>"
                )
                self.dupes_results_label.setText(results_text)
                self.preview_dupes_btn.setEnabled(True)
                self.remove_dupes_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to scan for duplicates: {e}')

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def preview_duplicates(self) -> None:
        """Show a dialog with the list of duplicate files."""
        if not hasattr(self, 'duplicate_data'):
            QMessageBox.warning(self, 'No Data', 'Please scan for duplicates first.')
            return

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Duplicate Calibration Frames Preview")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)

        layout = QVBoxLayout(dialog)

        # Info label
        total_count = sum(len(self.duplicate_data[t]) for t in ['darks', 'flats', 'bias'])
        info_label = QLabel(f"The following {total_count} files will be removed:")
        layout.addWidget(info_label)

        # Create table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['Type', 'Filename', 'Parameters', 'Path'])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Populate table
        row = 0
        for frame_type, frames in self.duplicate_data.items():
            for frame in frames:
                table.insertRow(row)

                # Type
                type_label = frame_type.capitalize()[:-1]  # Remove trailing 's'
                table.setItem(row, 0, QTableWidgetItem(type_label))

                # Filename
                filename = frame[2]  # filename column
                table.setItem(row, 1, QTableWidgetItem(filename))

                # Parameters
                if frame_type == 'darks':
                    params = f"Exp:{frame[3]:.1f}s, Temp:{frame[4]:.1f}°C, Bin{int(frame[5])}x{int(frame[6])}"
                elif frame_type == 'flats':
                    filt = frame[3] or "None"
                    params = f"Filter:{filt}, Date:{frame[4]}, Temp:{frame[5]:.1f}°C, Bin{int(frame[6])}x{int(frame[7])}"
                elif frame_type == 'bias':
                    params = f"Temp:{frame[3]:.1f}°C, Bin{int(frame[4])}x{int(frame[5])}"
                table.setItem(row, 2, QTableWidgetItem(params))

                # Path
                filepath = frame[1]
                table.setItem(row, 3, QTableWidgetItem(filepath or "N/A"))

                row += 1

        # Resize columns
        table.resizeColumnsToContents()
        layout.addWidget(table)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec()

    def remove_duplicates(self) -> None:
        """Remove duplicate calibration frames based on user selection."""
        if not hasattr(self, 'duplicate_data'):
            QMessageBox.warning(self, 'No Data', 'Please scan for duplicates first.')
            return

        total_count = sum(len(self.duplicate_data[t]) for t in ['darks', 'flats', 'bias'])
        if total_count == 0:
            QMessageBox.information(self, 'No Duplicates', 'No duplicate frames to remove.')
            return

        # Determine action
        delete_files = self.remove_db_and_files_radio.isChecked()
        action_text = "remove from database AND delete files from disk" if delete_files else "remove from database only"

        # Confirm
        reply = QMessageBox.question(
            self, 'Confirm Removal',
            f'Are you sure you want to {action_text}?\n\n'
            f'This will affect {total_count} calibration frames.\n\n'
            f'Individual frames will be removed where master frames exist.\n'
            f'Master frames will NOT be affected.\n\n'
            f'This action cannot be undone!',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            removed_count = 0
            deleted_files_count = 0
            errors = []

            # Collect all IDs and filepaths
            all_frames = []
            for frame_type in ['darks', 'flats', 'bias']:
                for frame in self.duplicate_data[frame_type]:
                    file_id = frame[0]
                    filepath = frame[1]
                    all_frames.append((file_id, filepath))

            # Remove from database and optionally delete files
            for file_id, filepath in all_frames:
                try:
                    # Remove from database
                    cursor.execute('DELETE FROM xisf_files WHERE id = ?', (file_id,))
                    removed_count += 1

                    # Delete file if requested
                    if delete_files and filepath and os.path.exists(filepath):
                        os.remove(filepath)
                        deleted_files_count += 1

                        # Try to clean up empty directories
                        try:
                            parent_dir = os.path.dirname(filepath)
                            if parent_dir and os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                                os.rmdir(parent_dir)
                        except:
                            pass  # Ignore cleanup errors

                except Exception as e:
                    errors.append(f"File ID {file_id}: {str(e)}")

            conn.commit()
            conn.close()

            # Show results
            message = f'Successfully removed {removed_count} duplicate frame(s) from database.'
            if delete_files:
                message += f'\n{deleted_files_count} file(s) deleted from disk.'

            if errors:
                message += f'\n\nErrors encountered:\n' + '\n'.join(errors[:5])
                if len(errors) > 5:
                    message += f'\n... and {len(errors) - 5} more'
                QMessageBox.warning(self, 'Completed with Errors', message)
            else:
                QMessageBox.information(self, 'Success', message)

            # Clear duplicate data and reset UI
            self.duplicate_data = None
            self.dupes_results_label.setText("No scan performed yet")
            self.preview_dupes_btn.setEnabled(False)
            self.remove_dupes_btn.setEnabled(False)

            # Log to import tab if available
            if self.import_log_widget:
                self.import_log_widget.append(f'\nRemoved {removed_count} duplicate calibration frames')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to remove duplicates: {e}')
