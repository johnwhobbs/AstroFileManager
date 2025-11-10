#!/usr/bin/env python3
"""
AstroFileManager - XISF File Management for Astrophotography
A PyQt6-based application for cataloging, organizing, and managing XISF astrophotography files.
"""

import sys
import os
import sqlite3
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QProgressBar, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QRadioButton, QButtonGroup, QGroupBox, QComboBox,
    QLineEdit, QMenu
)
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
import xisf
import re

# Import constants
from constants import (
    TEMP_TOLERANCE_DARKS, TEMP_TOLERANCE_FLATS, TEMP_TOLERANCE_BIAS,
    EXPOSURE_TOLERANCE, MIN_FRAMES_RECOMMENDED, MIN_FRAMES_ACCEPTABLE,
    IMPORT_BATCH_SIZE, DATE_OFFSET_HOURS
)

# Import core business logic modules
from core.database import DatabaseManager
from core.calibration import CalibrationMatcher

# Import import/export modules
from import_export.csv_exporter import CSVExporter

# Import UI modules
from ui.import_tab import ImportTab
from ui.settings_tab import SettingsTab
from ui.maintenance_tab import MaintenanceTab
from ui.sessions_tab import SessionsTab
from ui.analytics_tab import AnalyticsTab
from ui.view_catalog_tab import ViewCatalogTab


def generate_organized_path(repo_path, obj, filt, imgtyp, exp, temp, xbin, ybin, date, original_filename):
    """Generate the organized path and filename for a file"""
    # Sanitize values
    obj = obj or "Unknown"
    filt = filt or "NoFilter"
    imgtyp = imgtyp or "Unknown"
    date = date or "0000-00-00"

    # Determine binning string
    if xbin and ybin:
        try:
            binning = f"Bin{int(float(xbin))}x{int(float(ybin))}"
        except (ValueError, TypeError):
            binning = "Bin1x1"
    else:
        binning = "Bin1x1"

    # Determine temp string (round to nearest degree)
    if temp is not None:
        try:
            temp_float = float(temp)
            temp_str = f"{int(round(temp_float))}C"
        except (ValueError, TypeError):
            temp_str = "0C"
    else:
        temp_str = "0C"

    # Extract sequence number from original filename if possible
    seq_match = re.search(r'_(\d+)\.(xisf|fits?)$', original_filename, re.IGNORECASE)
    seq = seq_match.group(1) if seq_match else "001"

    # Determine file type and path structure
    if 'light' in imgtyp.lower():
        # Lights/[Object]/[Filter]/[filename]
        subdir = os.path.join("Lights", obj, filt)
        try:
            exp_str = f"{int(float(exp))}s" if exp else "0s"
        except (ValueError, TypeError):
            exp_str = "0s"
        new_filename = f"{date}_{obj}_{filt}_{exp_str}_{temp_str}_{binning}_{seq}.xisf"

    elif 'dark' in imgtyp.lower():
        # Calibration/Darks/[exp]_[temp]_[binning]/[filename]
        try:
            exp_str = f"{int(float(exp))}s" if exp else "0s"
        except (ValueError, TypeError):
            exp_str = "0s"
        subdir = os.path.join("Calibration", "Darks", f"{exp_str}_{temp_str}_{binning}")
        new_filename = f"{date}_Dark_{exp_str}_{temp_str}_{binning}_{seq}.xisf"

    elif 'flat' in imgtyp.lower():
        # Calibration/Flats/[date]/[filter]_[temp]_[binning]/[filename]
        subdir = os.path.join("Calibration", "Flats", date, f"{filt}_{temp_str}_{binning}")
        new_filename = f"{date}_Flat_{filt}_{temp_str}_{binning}_{seq}.xisf"

    elif 'bias' in imgtyp.lower():
        # Calibration/Bias/[temp]_[binning]/[filename]
        subdir = os.path.join("Calibration", "Bias", f"{temp_str}_{binning}")
        new_filename = f"{date}_Bias_{temp_str}_{binning}_{seq}.xisf"

    else:
        # Unknown type - put in root with original structure
        subdir = "Uncategorized"
        new_filename = original_filename

    return os.path.join(repo_path, subdir, new_filename)


class XISFCatalogGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = 'xisf_catalog.db'
        self.settings = QSettings('AstroFileManager', 'AstroFileManager')

        # Initialize core business logic components
        self.db = DatabaseManager(self.db_path)
        self.calibration = CalibrationMatcher(
            self.db,
            include_masters=True,
            temp_tolerance_darks=TEMP_TOLERANCE_DARKS,
            temp_tolerance_flats=TEMP_TOLERANCE_FLATS,
            temp_tolerance_bias=TEMP_TOLERANCE_BIAS,
            exposure_tolerance=EXPOSURE_TOLERANCE,
            min_frames_recommended=MIN_FRAMES_RECOMMENDED,
            min_frames_acceptable=MIN_FRAMES_ACCEPTABLE
        )

        self.init_ui()
        # Restore settings after all UI is created
        self.restore_settings()
        # Populate the View Catalog tab on startup (fixes Issue #44)
        self.view_tab.refresh_catalog_view()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('AstroFileManager')
        self.setGeometry(100, 100, 1000, 600)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Create tabs
        self.import_tab = ImportTab(self.db_path, self.settings)
        self.settings_tab = SettingsTab(self.settings)
        self.maintenance_tab = MaintenanceTab(self.db_path, self.settings, self.import_tab.log_text)
        self.sessions_tab = SessionsTab(self.db_path, self.db, self.calibration)
        self.view_tab = ViewCatalogTab(
            db_path=self.db_path,
            settings=self.settings,
            status_callback=self.statusBar().showMessage,
            reimport_callback=self.import_tab.start_import
        )
        self.analytics_tab = AnalyticsTab(self.db_path, self.settings)

        # Set cross-tab dependencies after all tabs are created
        self.import_tab.clear_db_btn = self.maintenance_tab.clear_db_btn
        self.clear_db_btn = self.maintenance_tab.clear_db_btn  # For backward compatibility

        tabs.addTab(self.view_tab, "View Catalog")
        tabs.addTab(self.sessions_tab, "Sessions")
        tabs.addTab(self.analytics_tab, "Analytics")
        tabs.addTab(self.import_tab, "Import Files")
        tabs.addTab(self.maintenance_tab, "Maintenance")
        tabs.addTab(self.settings_tab, "Settings")
        
        # Connect tab change to refresh
        tabs.currentChanged.connect(self.on_tab_changed)
    

    def on_keyword_changed(self):
        """Update the current value dropdown when keyword selection changes"""
        keyword = self.keyword_combo.currentText()
        self.populate_current_values(keyword)
    
    def populate_current_values(self, keyword):
        """Populate the current value dropdown with existing values from the database"""
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
    
    def replace_values(self):
        """Replace values in the database"""
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

    def preview_organization(self):
        """Preview the file organization plan"""
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
    
    def execute_organization(self):
        """Execute the file organization"""
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
            import shutil
            
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

    def create_settings_tab(self):
        """Create the settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Image Repository Location
        repo_group = QGroupBox("Image Repository")
        repo_layout = QVBoxLayout()
        
        repo_info = QLabel("Set the location for your organized XISF files:")
        repo_layout.addWidget(repo_info)
        
        repo_path_layout = QHBoxLayout()
        repo_path_label = QLabel("Repository Path:")
        repo_path_label.setMinimumWidth(120)
        self.repo_path_input = QLineEdit()
        self.repo_path_input.setReadOnly(True)
        current_repo = self.settings.value('repository_path', '')
        if current_repo:
            # Standardize on forward slashes
            current_repo = current_repo.replace('\\', '/')
        self.repo_path_input.setText(current_repo)
        
        browse_repo_btn = QPushButton('Browse...')
        browse_repo_btn.clicked.connect(self.browse_repository)
        
        repo_path_layout.addWidget(repo_path_label)
        repo_path_layout.addWidget(self.repo_path_input)
        repo_path_layout.addWidget(browse_repo_btn)
        repo_layout.addLayout(repo_path_layout)
        
        repo_group.setLayout(repo_layout)
        layout.addWidget(repo_group)

        # Timezone settings group
        timezone_group = QGroupBox("Timezone")
        timezone_layout = QVBoxLayout()

        timezone_info = QLabel("Set your local timezone for DATE-OBS conversion:")
        timezone_layout.addWidget(timezone_info)

        timezone_help = QLabel("Used to convert UTC timestamps (DATE-OBS) to local time for session grouping.")
        timezone_help.setStyleSheet("color: #888888; font-size: 10px;")
        timezone_layout.addWidget(timezone_help)

        timezone_selector_layout = QHBoxLayout()
        timezone_label = QLabel("Timezone:")
        timezone_label.setMinimumWidth(120)
        self.timezone_combo = QComboBox()

        # Common timezones
        common_timezones = [
            'UTC',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'America/Phoenix',
            'America/Anchorage',
            'Pacific/Honolulu',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Europe/Rome',
            'Europe/Madrid',
            'Europe/Athens',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Hong_Kong',
            'Asia/Singapore',
            'Asia/Dubai',
            'Australia/Sydney',
            'Australia/Melbourne',
            'Australia/Perth',
            'Pacific/Auckland'
        ]

        self.timezone_combo.addItems(common_timezones)

        # Set current timezone
        current_timezone = self.settings.value('timezone', 'UTC')
        index = self.timezone_combo.findText(current_timezone)
        if index >= 0:
            self.timezone_combo.setCurrentIndex(index)

        save_timezone_btn = QPushButton('Save Timezone')
        save_timezone_btn.clicked.connect(self.save_timezone_setting)

        timezone_selector_layout.addWidget(timezone_label)
        timezone_selector_layout.addWidget(self.timezone_combo)
        timezone_selector_layout.addWidget(save_timezone_btn)
        timezone_layout.addLayout(timezone_selector_layout)

        timezone_group.setLayout(timezone_layout)
        layout.addWidget(timezone_group)

        # Theme settings group
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout()
        
        # Radio buttons for theme selection
        self.theme_button_group = QButtonGroup()
        self.standard_theme_radio = QRadioButton("Standard Theme")
        self.dark_theme_radio = QRadioButton("Dark Theme")
        
        self.theme_button_group.addButton(self.standard_theme_radio, 0)
        self.theme_button_group.addButton(self.dark_theme_radio, 1)
        
        theme_layout.addWidget(self.standard_theme_radio)
        theme_layout.addWidget(self.dark_theme_radio)
        
        # Set current theme
        current_theme = self.settings.value('theme', 'dark')
        if current_theme == 'standard':
            self.standard_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # OK button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton('Apply Theme')
        ok_button.clicked.connect(self.apply_theme_setting)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return widget
    
    def browse_repository(self):
        """Browse for repository location"""
        current_path = self.repo_path_input.text()
        directory = QFileDialog.getExistingDirectory(
            self, 'Select Image Repository Location', 
            current_path if current_path else ''
        )
        
        if directory:
            # Normalize path to use OS-specific separators
            directory = os.path.normpath(directory)
            self.repo_path_input.setText(directory)
            self.settings.setValue('repository_path', directory)
            QMessageBox.information(
                self, 'Repository Path Updated',
                f'Image repository location set to:\n{directory}'
            )
    
    def save_timezone_setting(self):
        """Save the selected timezone"""
        timezone = self.timezone_combo.currentText()
        self.settings.setValue('timezone', timezone)
        QMessageBox.information(
            self,
            'Timezone Saved',
            f'Timezone set to: {timezone}\n\nThis will be used for converting DATE-OBS timestamps.'
        )

    def apply_theme_setting(self):
        """Apply the selected theme"""
        if self.standard_theme_radio.isChecked():
            theme = 'standard'
        else:
            theme = 'dark'

        # Save theme preference
        self.settings.setValue('theme', theme)

        # Show message that restart is needed
        QMessageBox.information(
            self,
            'Theme Changed',
            'Theme has been changed. Please restart the application for the changes to take effect.'
        )
    
    def connect_signals(self):
        """Connect signals after all widgets are created"""
        # Connect column resize signals to save settings
        self.view_tab.catalog_tree.header().sectionResized.connect(self.save_settings)
        self.sessions_tab.sessions_tree.header().sectionResized.connect(self.save_settings)
    
    def save_settings(self):
        """Save window size and column widths"""
        # Save window geometry
        self.settings.setValue('geometry', self.saveGeometry())

        # Save catalog tree column widths
        for i in range(self.view_tab.catalog_tree.columnCount()):
            self.settings.setValue(f'catalog_tree_col_{i}', self.view_tab.catalog_tree.columnWidth(i))

        # Save sessions tree column widths
        for i in range(self.sessions_tab.sessions_tree.columnCount()):
            self.settings.setValue(f'sessions_tree_col_{i}', self.sessions_tab.sessions_tree.columnWidth(i))
    
    def restore_settings(self):
        """Restore window size and column widths"""
        # Restore window geometry
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)

        # Restore catalog tree column widths
        for i in range(self.view_tab.catalog_tree.columnCount()):
            width = self.settings.value(f'catalog_tree_col_{i}')
            if width is not None:
                self.view_tab.catalog_tree.setColumnWidth(i, int(width))

        # Restore sessions tree column widths
        for i in range(self.sessions_tab.sessions_tree.columnCount()):
            width = self.settings.value(f'sessions_tree_col_{i}')
            if width is not None:
                self.sessions_tab.sessions_tree.setColumnWidth(i, int(width))

        # Connect signals after restoring settings to avoid triggering saves during restore
        self.connect_signals()
    
    def closeEvent(self, event):
        """Save settings when closing"""
        self.save_settings()
        event.accept()
    
    def on_tab_changed(self, index):
        """Handle tab change"""
        if index == 0:  # View Catalog tab
            self.view_tab.refresh_catalog_view()
        elif index == 1:  # Sessions tab
            self.sessions_tab.refresh_sessions()
        elif index == 2:  # Analytics tab
            self.analytics_tab.refresh_analytics()
        elif index == 4:  # Maintenance tab
            # Populate current values when maintenance tab is opened
            keyword = self.maintenance_tab.keyword_combo.currentText()
            self.maintenance_tab.populate_current_values(keyword)



def main():
    app = QApplication(sys.argv)
    
    # Load theme setting
    settings = QSettings('AstroFileManager', 'AstroFileManager')
    theme = settings.value('theme', 'dark')
    
    # Apply theme
    if theme == 'dark':
        apply_dark_theme(app)
    else:
        apply_standard_theme(app)
    
    window = XISFCatalogGUI()
    window.show()
    sys.exit(app.exec())


def apply_dark_theme(app):
    """Apply dark theme to the application"""
    app.setStyle('Fusion')
    
    dark_palette = app.palette()
    
    # Define dark theme colors
    dark_palette.setColor(dark_palette.ColorRole.Window, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Base, Qt.GlobalColor.black)
    dark_palette.setColor(dark_palette.ColorRole.AlternateBase, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Button, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(dark_palette.ColorRole.Link, Qt.GlobalColor.blue)
    dark_palette.setColor(dark_palette.ColorRole.Highlight, Qt.GlobalColor.blue)
    dark_palette.setColor(dark_palette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    
    app.setPalette(dark_palette)
    
    # Additional stylesheet for better appearance
    app.setStyleSheet("""
        QToolTip {
            color: #ffffff;
            background-color: #2a2a2a;
            border: 1px solid white;
        }
        QPushButton {
            background-color: #404040;
            border: 1px solid #555555;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #505050;
        }
        QPushButton:pressed {
            background-color: #303030;
        }
        QTreeWidget, QTableWidget {
            background-color: #2a2a2a;
            alternate-background-color: #353535;
        }
        QHeaderView::section {
            background-color: #404040;
            padding: 4px;
            border: 1px solid #555555;
            font-weight: bold;
        }
        QProgressBar {
            border: 1px solid #555555;
            border-radius: 3px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #3a7bd5;
        }
        QTextEdit {
            background-color: #2a2a2a;
            border: 1px solid #555555;
        }
        QGroupBox {
            border: 1px solid #555555;
            margin-top: 0.5em;
            padding-top: 0.5em;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
    """)


def apply_standard_theme(app):
    """Apply standard theme to the application"""
    # Use the system default style
    app.setStyle('Fusion')
    
    # Use system default palette - no custom colors
    app.setPalette(app.style().standardPalette())
    
    # Minimal stylesheet for consistency
    app.setStyleSheet("""
        QPushButton {
            padding: 5px;
        }
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 3px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            margin-top: 0.5em;
            padding-top: 0.5em;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
    """)


if __name__ == '__main__':
    main()
