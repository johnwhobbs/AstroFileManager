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
    QListWidgetItem, QDoubleSpinBox
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
            'Are you sure you want to delete all records from the database?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
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
