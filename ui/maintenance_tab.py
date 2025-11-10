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
    QLabel, QTextEdit, QGroupBox, QComboBox, QLineEdit
)
from PyQt6.QtCore import QSettings


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
        """Replace values in the database."""
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
        reply = QMessageBox.question(
            self, 'Confirm Replacement',
            f'Replace all occurrences of:\n\n'
            f'Keyword: {keyword}\n'
            f'Current Value: "{current_value}"\n'
            f'Replacement Value: "{replacement_value}"\n\n'
            f'Are you sure?',
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
                if column:
                    cursor.execute(f'UPDATE xisf_files SET {column} = ? WHERE {column} = ?',
                                   (replacement_value, current_value))
                    rows_affected = cursor.rowcount
                    conn.commit()

                    QMessageBox.information(
                        self, 'Success',
                        f'Successfully replaced {rows_affected} occurrence(s).'
                    )

                    # Refresh the current values dropdown
                    self.populate_current_values(keyword)
                    self.replacement_input.clear()

                conn.close()
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to replace values: {e}')

    def preview_organization(self) -> None:
        """Preview the file organization plan."""
        from utils.file_organizer import generate_organized_path

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
