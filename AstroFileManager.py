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
        self.refresh_catalog_view()

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
        self.view_tab = self.create_view_tab()
        self.sessions_tab = self.create_sessions_tab()
        self.analytics_tab = self.create_analytics_tab()
        self.maintenance_tab = self.create_maintenance_tab()
        self.settings_tab = self.create_settings_tab()

        # Set cross-tab dependencies after all tabs are created
        self.import_tab.clear_db_btn = self.clear_db_btn

        tabs.addTab(self.view_tab, "View Catalog")
        tabs.addTab(self.sessions_tab, "Sessions")
        tabs.addTab(self.analytics_tab, "Analytics")
        tabs.addTab(self.import_tab, "Import Files")
        tabs.addTab(self.maintenance_tab, "Maintenance")
        tabs.addTab(self.settings_tab, "Settings")
        
        # Connect tab change to refresh
        tabs.currentChanged.connect(self.on_tab_changed)
    

    def create_sessions_tab(self):
        """Create the sessions tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Top controls section
        controls_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton('Refresh Sessions')
        refresh_btn.clicked.connect(self.refresh_sessions)
        controls_layout.addWidget(refresh_btn)

        # Status filter dropdown
        controls_layout.addWidget(QLabel('Status Filter:'))
        self.session_status_filter = QComboBox()
        self.session_status_filter.addItems(['All', 'Complete', 'Partial', 'Missing'])
        self.session_status_filter.currentTextChanged.connect(self.refresh_sessions)
        controls_layout.addWidget(self.session_status_filter)

        # Missing only checkbox
        self.missing_only_checkbox = QRadioButton('Missing Only')
        self.missing_only_checkbox.toggled.connect(self.refresh_sessions)
        controls_layout.addWidget(self.missing_only_checkbox)

        # Include masters checkbox
        self.include_masters_checkbox = QRadioButton('Include Masters')
        self.include_masters_checkbox.setChecked(True)
        self.include_masters_checkbox.toggled.connect(self.refresh_sessions)
        controls_layout.addWidget(self.include_masters_checkbox)

        # Export button
        export_btn = QPushButton('Export Report')
        export_btn.clicked.connect(self.export_session_report)
        controls_layout.addWidget(export_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Statistics panel
        stats_group = QGroupBox("Session Statistics")
        stats_layout = QHBoxLayout()

        self.total_sessions_label = QLabel('Total Sessions: 0')
        stats_layout.addWidget(self.total_sessions_label)

        self.complete_sessions_label = QLabel('Complete: 0')
        stats_layout.addWidget(self.complete_sessions_label)

        self.partial_sessions_label = QLabel('Partial: 0')
        stats_layout.addWidget(self.partial_sessions_label)

        self.missing_sessions_label = QLabel('Missing: 0')
        stats_layout.addWidget(self.missing_sessions_label)

        self.completion_rate_label = QLabel('Completion Rate: 0%')
        stats_layout.addWidget(self.completion_rate_label)

        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Sessions tree widget
        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setColumnCount(6)
        self.sessions_tree.setHeaderLabels([
            'Session', 'Status', 'Light Frames', 'Darks', 'Bias', 'Flats'
        ])
        self.sessions_tree.setColumnWidth(0, 250)
        self.sessions_tree.setColumnWidth(1, 100)
        self.sessions_tree.setColumnWidth(2, 120)
        self.sessions_tree.setColumnWidth(3, 150)
        self.sessions_tree.setColumnWidth(4, 150)
        self.sessions_tree.setColumnWidth(5, 150)
        self.sessions_tree.itemClicked.connect(self.on_session_clicked)
        layout.addWidget(self.sessions_tree)

        # Session details panel
        details_group = QGroupBox("Session Details")
        details_layout = QVBoxLayout()

        self.session_details_text = QTextEdit()
        self.session_details_text.setReadOnly(True)
        self.session_details_text.setMaximumHeight(200)
        details_layout.addWidget(self.session_details_text)

        # Recommendations panel
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMaximumHeight(150)
        self.recommendations_text.setPlaceholderText('Recommendations will appear here...')
        details_layout.addWidget(QLabel('Recommendations:'))
        details_layout.addWidget(self.recommendations_text)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        return widget

    def create_analytics_tab(self):
        """Create the analytics tab with activity heatmap"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Year selector
        year_layout = QHBoxLayout()
        year_label = QLabel("Year:")
        self.year_combo = QComboBox()
        self.year_combo.currentTextChanged.connect(self.refresh_analytics)
        year_layout.addWidget(year_label)
        year_layout.addWidget(self.year_combo)
        year_layout.addStretch()
        
        refresh_analytics_btn = QPushButton('Refresh')
        refresh_analytics_btn.clicked.connect(self.refresh_analytics)
        year_layout.addWidget(refresh_analytics_btn)
        
        layout.addLayout(year_layout)
        
        # Statistics cards
        self.analytics_stats_widget = QWidget()
        self.analytics_stats_layout = QHBoxLayout(self.analytics_stats_widget)
        self.analytics_stats_layout.setSpacing(10)
        layout.addWidget(self.analytics_stats_widget)
        
        # Heatmap container
        heatmap_label = QLabel("Imaging Activity Calendar")
        heatmap_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(heatmap_label)
        
        self.heatmap_widget = QWidget()
        self.heatmap_layout = QHBoxLayout(self.heatmap_widget)
        self.heatmap_layout.setSpacing(3)
        self.heatmap_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.heatmap_widget)
        
        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.addStretch()
        legend_layout.addWidget(QLabel("Less"))
        
        for level in range(5):
            legend_cell = QLabel()
            legend_cell.setFixedSize(15, 15)
            legend_cell.setStyleSheet(self.get_heatmap_color_style(level))
            legend_layout.addWidget(legend_cell)
        
        legend_layout.addWidget(QLabel("More"))
        legend_layout.addStretch()
        layout.addLayout(legend_layout)
        
        layout.addStretch()
        
        return widget
    
    def get_heatmap_color_style(self, level):
        """Get stylesheet for heatmap cell based on activity level"""
        # Check current theme
        current_theme = self.settings.value('theme', 'dark')
        
        if current_theme == 'dark':
            # Dark theme colors - green scale
            colors = {
                0: "#2d2d2d",
                1: "#0e4429",
                2: "#006d32",
                3: "#26a641",
                4: "#39d353"
            }
        else:
            # Standard theme colors - blue scale
            colors = {
                0: "#ebedf0",
                1: "#9be9a8",
                2: "#40c463",
                3: "#30a14e",
                4: "#216e39"
            }
        
        return f"background-color: {colors.get(level, colors[0])}; border-radius: 2px;"
    
    def refresh_analytics(self):
        """Refresh the analytics view"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get available years
            cursor.execute('SELECT DISTINCT strftime("%Y", date_loc) as year FROM xisf_files WHERE date_loc IS NOT NULL ORDER BY year DESC')
            years = [row[0] for row in cursor.fetchall()]
            
            # Populate year combo if empty or update selection
            current_year = self.year_combo.currentText()
            self.year_combo.blockSignals(True)
            self.year_combo.clear()
            if years:
                self.year_combo.addItems(years)
                if current_year in years:
                    self.year_combo.setCurrentText(current_year)
            self.year_combo.blockSignals(False)
            
            selected_year = self.year_combo.currentText()
            if not selected_year:
                conn.close()
                return
            
            # Get activity data for the selected year
            cursor.execute('''
                SELECT 
                    date_loc,
                    SUM(exposure) / 3600.0 as hours
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
                    AND exposure IS NOT NULL
                    AND (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                GROUP BY date_loc
            ''', (selected_year,))
            
            activity_data = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Calculate statistics
            cursor.execute('''
                SELECT COUNT(DISTINCT date_loc) as sessions
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
            ''', (selected_year,))
            total_sessions = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT SUM(exposure) / 3600.0 as total_hours
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND exposure IS NOT NULL
                    AND (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
            ''', (selected_year,))
            total_hours = cursor.fetchone()[0] or 0
            
            avg_hours = total_hours / total_sessions if total_sessions > 0 else 0
            
            # Most active month
            cursor.execute('''
                SELECT 
                    strftime("%m", date_loc) as month,
                    COUNT(DISTINCT date_loc) as sessions
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
                GROUP BY month
                ORDER BY sessions DESC
                LIMIT 1
            ''', (selected_year,))
            
            most_active = cursor.fetchone()
            if most_active:
                month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                most_active_month = month_names[int(most_active[0])]
                sessions_in_month = most_active[1]
            else:
                most_active_month = 'N/A'
                sessions_in_month = 0
            
            # Calculate longest streak
            all_dates = sorted([d for d in activity_data.keys()])
            longest_streak = 0
            current_streak = 0
            
            for i, date in enumerate(all_dates):
                if i == 0:
                    current_streak = 1
                else:
                    prev_date = datetime.strptime(all_dates[i-1], '%Y-%m-%d')
                    curr_date = datetime.strptime(date, '%Y-%m-%d')
                    if (curr_date - prev_date).days == 1:
                        current_streak += 1
                    else:
                        longest_streak = max(longest_streak, current_streak)
                        current_streak = 1
            longest_streak = max(longest_streak, current_streak)
            
            # Days since last session
            cursor.execute('''
                SELECT MAX(date_loc)
                FROM xisf_files
                WHERE date_loc IS NOT NULL
            ''')
            last_session = cursor.fetchone()[0]
            if last_session:
                last_date = datetime.strptime(last_session, '%Y-%m-%d')
                today = datetime.now()
                days_since = (today - last_date).days
            else:
                days_since = 0
            
            conn.close()
            
            # Update statistics cards
            self.update_analytics_stats(
                total_sessions, total_hours, avg_hours,
                longest_streak, most_active_month, sessions_in_month, days_since
            )
            
            # Update heatmap
            self.update_heatmap(selected_year, activity_data)
            
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh analytics: {e}')
    
    def update_analytics_stats(self, sessions, total_hours, avg_hours, streak, month, month_sessions, days_since):
        """Update the analytics statistics cards"""
        # Clear existing cards
        while self.analytics_stats_layout.count():
            child = self.analytics_stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Check current theme
        current_theme = self.settings.value('theme', 'dark')
        
        if current_theme == 'dark':
            card_bg = "#2d2d2d"
            value_color = "#39d353"
            label_color = "#888"
        else:
            card_bg = "#f6f8fa"
            value_color = "#0969da"
            label_color = "#57606a"
        
        stats = [
            (sessions, "Clear Nights Imaged"),
            (f"{total_hours:.1f}", "Total Hours"),
            (f"{avg_hours:.1f}", "Avg Hours/Session"),
            (streak, "Longest Streak (days)"),
            (month, "Most Active Month"),
            (month_sessions, f"Sessions in {month}"),
            (days_since, "Days Since Last Session")
        ]
        
        for value, label in stats:
            card = QWidget()
            card.setStyleSheet(f"background-color: {card_bg}; border-radius: 8px; padding: 10px; border: 1px solid #d0d7de;")
            card_layout = QVBoxLayout(card)
            
            value_label = QLabel(str(value))
            value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {value_color};")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            desc_label = QLabel(label)
            desc_label.setStyleSheet(f"font-size: 11px; color: {label_color};")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            
            card_layout.addWidget(value_label)
            card_layout.addWidget(desc_label)
            
            self.analytics_stats_layout.addWidget(card)
    
    def update_heatmap(self, year, activity_data):
        """Update the heatmap visualization"""
        # Clear existing heatmap
        while self.heatmap_layout.count():
            child = self.heatmap_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        start_date = datetime(int(year), 1, 1)
        end_date = datetime(int(year), 12, 31)
        
        # Start on Sunday before the year starts
        first_sunday = start_date - timedelta(days=start_date.weekday() + 1 if start_date.weekday() != 6 else 0)
        
        current_date = first_sunday
        current_week = None
        
        while current_date <= end_date:
            # Start new week column on Sunday
            if current_date.weekday() == 6:  # Sunday
                if current_week:
                    self.heatmap_layout.addWidget(current_week)
                current_week = QWidget()
                week_layout = QVBoxLayout(current_week)
                week_layout.setSpacing(3)
                week_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create day cell
            cell = QLabel()
            cell.setFixedSize(15, 15)
            
            date_str = current_date.strftime('%Y-%m-%d')
            
            if current_date < start_date:
                # Days before year starts - invisible
                cell.setStyleSheet("background-color: transparent;")
            else:
                hours = activity_data.get(date_str, 0)
                level = self.get_activity_level(hours)
                cell.setStyleSheet(self.get_heatmap_color_style(level))
                cell.setToolTip(f"{current_date.strftime('%b %d, %Y')}\n{hours:.1f} hours")
            
            week_layout.addWidget(cell)
            current_date += timedelta(days=1)
        
        # Add final week
        if current_week:
            self.heatmap_layout.addWidget(current_week)
    
    def get_activity_level(self, hours):
        """Determine activity level based on hours"""
        if hours == 0:
            return 0
        elif hours < 2:
            return 1
        elif hours < 4:
            return 2
        elif hours < 6:
            return 3
        else:
            return 4
    
    def create_maintenance_tab(self):
        """Create the maintenance tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
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

        return widget
    
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
        self.catalog_tree.header().sectionResized.connect(self.save_settings)
        self.sessions_tree.header().sectionResized.connect(self.save_settings)
    
    def save_settings(self):
        """Save window size and column widths"""
        # Save window geometry
        self.settings.setValue('geometry', self.saveGeometry())

        # Save catalog tree column widths
        for i in range(self.catalog_tree.columnCount()):
            self.settings.setValue(f'catalog_tree_col_{i}', self.catalog_tree.columnWidth(i))

        # Save sessions tree column widths
        for i in range(self.sessions_tree.columnCount()):
            self.settings.setValue(f'sessions_tree_col_{i}', self.sessions_tree.columnWidth(i))
    
    def restore_settings(self):
        """Restore window size and column widths"""
        # Restore window geometry
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)

        # Restore catalog tree column widths
        for i in range(self.catalog_tree.columnCount()):
            width = self.settings.value(f'catalog_tree_col_{i}')
            if width is not None:
                self.catalog_tree.setColumnWidth(i, int(width))

        # Restore sessions tree column widths
        for i in range(self.sessions_tree.columnCount()):
            width = self.settings.value(f'sessions_tree_col_{i}')
            if width is not None:
                self.sessions_tree.setColumnWidth(i, int(width))

        # Connect signals after restoring settings to avoid triggering saves during restore
        self.connect_signals()
    
    def closeEvent(self, event):
        """Save settings when closing"""
        self.save_settings()
        event.accept()
    
    def create_view_tab(self):
        """Create the view tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

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

        return widget

    def create_stat_card(self, title, value_label):
        """Create a statistics card widget"""
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

    def filter_catalog_tree(self):
        """Filter the catalog tree based on search text"""
        search_text = self.catalog_search_box.text().lower()

        def filter_item(item):
            """Recursively filter tree items"""
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

    def show_catalog_context_menu(self, position):
        """Show context menu for catalog tree items"""
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

    def show_file_path(self, item):
        """Show the full file path in a message box"""
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

    def copy_file_path_to_clipboard(self, item):
        """Copy file path to clipboard"""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                from PyQt6.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(result[0])
                self.status_label.setText(f'Path copied to clipboard: {filename}')
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to copy path: {e}')

    def open_file_location(self, item):
        """Open the file location in file manager"""
        filename = item.text(0)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            conn.close()

            if result:
                import subprocess
                import platform
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

    def show_file_details(self, item):
        """Show detailed file information in a dialog"""
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
                details = f"""File: {filename}
Path: {result[0]}

Telescope: {result[1] or 'N/A'}
Instrument: {result[2] or 'N/A'}
Object: {result[3] or 'N/A'}
Filter: {result[4] or 'N/A'}
Image Type: {result[5] or 'N/A'}
Exposure: {result[6]:.1f}s if result[6] else 'N/A'
Temperature: {result[7]:.1f}°C if result[7] is not None else 'N/A'
Binning: {int(result[8])}x{int(result[9])} if result[8] and result[9] else 'N/A'
Date: {result[10] or 'N/A'}
Imported: {result[11] or 'N/A'}
"""
                QMessageBox.information(self, 'File Details', details)
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to retrieve file details: {e}')

    def delete_file_from_database(self, item):
        """Delete a file from the database"""
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

    def reimport_file(self, item):
        """Re-import a file"""
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
                    self.start_import([filepath])
                else:
                    QMessageBox.warning(self, 'File Not Found', f'File does not exist:\n{filepath}')
            else:
                QMessageBox.warning(self, 'Not Found', f'File not found in database: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to re-import file: {e}')

    def export_tree_group_to_csv(self, item):
        """Export a tree group (and its children) to CSV"""
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

    def export_catalog_to_csv(self):
        """Export entire catalog to CSV"""
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

    def clear_database(self):
        """Clear all records from the database"""
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
                
                self.log_text.append('\nDatabase cleared successfully!')
                QMessageBox.information(self, 'Success', 'Database cleared successfully!')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to clear database: {e}')

    def update_catalog_statistics(self, cursor):
        """Update the catalog statistics panel"""
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

    def get_item_color(self, imagetyp):
        """Get color for tree item based on image type"""
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

    def refresh_catalog_view(self):
        """Refresh the catalog view tree"""
        try:
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

            self.catalog_tree.clear()

            # ===== LIGHT FRAMES SECTION =====
            # Skip light frames section if filtering to calibration only
            if imagetype_filter not in ['Dark', 'Flat', 'Bias', 'Master']:
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

                # Get total light frame counts
                cursor.execute(f'''
                    SELECT COUNT(*), SUM(exposure) / 3600.0
                    FROM xisf_files
                    WHERE {where_clause}
                ''', params)
                light_total_count, light_total_exp = cursor.fetchone()
                light_total_exp = light_total_exp or 0

                light_frames_root = QTreeWidgetItem(self.catalog_tree)
                light_frames_root.setText(0, f"Light Frames ({light_total_count} files, {light_total_exp:.1f}h)")
                light_frames_root.setFlags(light_frames_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
                # Make parent nodes bold
                font = light_frames_root.font(0)
                font.setBold(True)
                light_frames_root.setFont(0, font)

                # Get all objects (light frames only)
                cursor.execute(f'''
                    SELECT
                        object,
                        COUNT(*) as file_count,
                        SUM(exposure) as total_exposure
                    FROM xisf_files
                    WHERE {where_clause}
                    GROUP BY object
                    ORDER BY object
                ''', params)

            objects = cursor.fetchall()

            for obj_name, obj_file_count, obj_total_exp in objects:
                # Create object node with aggregate info
                obj_exp_hrs = (obj_total_exp or 0) / 3600.0
                obj_item = QTreeWidgetItem(light_frames_root)
                obj_item.setText(0, f"{obj_name or 'Unknown'} ({obj_file_count} files, {obj_exp_hrs:.1f}h)")
                obj_item.setFlags(obj_item.flags() | Qt.ItemFlag.ItemIsAutoTristate)

                # Get all filters for this object
                cursor.execute('''
                    SELECT
                        filter,
                        COUNT(*) as file_count,
                        SUM(exposure) as total_exposure
                    FROM xisf_files
                    WHERE object = ?
                    GROUP BY filter
                    ORDER BY filter
                ''', (obj_name,))

                filters = cursor.fetchall()

                for filter_name, filter_file_count, filter_total_exp in filters:
                    # Create filter node with aggregate info
                    filter_exp_hrs = (filter_total_exp or 0) / 3600.0
                    filter_item = QTreeWidgetItem(obj_item)
                    filter_item.setText(0, f"{filter_name or 'No Filter'} ({filter_file_count} files, {filter_exp_hrs:.1f}h)")
                    filter_item.setText(2, filter_name or 'No Filter')  # Show filter in Filter column too

                    # Get all dates for this object and filter
                    cursor.execute('''
                        SELECT
                            date_loc,
                            COUNT(*) as file_count,
                            SUM(exposure) as total_exposure
                        FROM xisf_files
                        WHERE object = ? AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                        GROUP BY date_loc
                        ORDER BY date_loc DESC
                    ''', (obj_name, filter_name, filter_name))

                    dates = cursor.fetchall()

                    for date_val, date_file_count, date_total_exp in dates:
                        # Create date node with aggregate info
                        date_exp_hrs = (date_total_exp or 0) / 3600.0
                        date_item = QTreeWidgetItem(filter_item)
                        date_item.setText(0, f"{date_val or 'No Date'} ({date_file_count} files, {date_exp_hrs:.1f}h)")
                        date_item.setText(6, date_val or 'No Date')  # Show date in Date column too

                        # Get all files for this object, filter, and date
                        cursor.execute('''
                            SELECT
                                filename,
                                imagetyp,
                                exposure,
                                telescop,
                                instrume,
                                date_loc,
                                filter,
                                ccd_temp,
                                xbinning,
                                ybinning
                            FROM xisf_files
                            WHERE object = ?
                                AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                                AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                            ORDER BY filename
                        ''', (obj_name, filter_name, filter_name, date_val, date_val))

                        files = cursor.fetchall()

                        for filename, imagetyp, exposure, telescop, instrume, date_loc, filt, temp, xbin, ybin in files:
                            # Create file node with all columns
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

                            # Apply color coding based on image type
                            color = self.get_item_color(imagetyp)
                            if color:
                                for col in range(9):
                                    file_item.setBackground(col, QBrush(color))

            # ===== CALIBRATION FRAMES SECTION =====
            # Skip calibration frames if filtering to Light only
            if imagetype_filter not in ['Light']:
                # Get total calibration counts
                calib_where = []
                calib_params = []
                if imagetype_filter in ['Dark', 'Flat', 'Bias', 'Master']:
                    if imagetype_filter == 'Master':
                        calib_where.append('imagetyp LIKE ?')
                        calib_params.append('%Master%')
                    else:
                        calib_where.append(f'imagetyp LIKE ?')
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

                calib_root = QTreeWidgetItem(self.catalog_tree)
                calib_root.setText(0, f"Calibration Frames ({calib_total_count} files)")
                calib_root.setFlags(calib_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
                font = calib_root.font(0)
                font.setBold(True)
                calib_root.setFont(0, font)

                # ----- DARK FRAMES: exposure_temp_binning → date → files -----
                if imagetype_filter in ['All', 'Dark', 'Master']:
                    dark_where = 'imagetyp LIKE "%Dark%" AND object IS NULL'
                    if imagetype_filter == 'Master':
                        dark_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Dark%" AND object IS NULL'

                    cursor.execute(f'SELECT COUNT(*) FROM xisf_files WHERE {dark_where}')
                    dark_count = cursor.fetchone()[0]

                    if dark_count > 0:
                        dark_root = QTreeWidgetItem(calib_root)
                        dark_root.setText(0, f"Dark Frames ({dark_count} files)")
                        dark_root.setFlags(dark_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            cursor.execute('''
                SELECT
                    exposure,
                    ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                    xbinning,
                    ybinning,
                    COUNT(*) as file_count
                FROM xisf_files
                WHERE imagetyp LIKE '%Dark%' AND object IS NULL
                GROUP BY exposure, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning
                ORDER BY exposure, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning
            ''')

            dark_groups = cursor.fetchall()

            for exp, temp, xbin, ybin, count in dark_groups:
                # Create dark group node (e.g., "300s_-10C_Bin1x1 (25 files)")
                exp_str = f"{int(exp)}s" if exp else "0s"
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
                group_name = f"{exp_str}_{temp_str}_{binning} ({count} files)"

                dark_group_item = QTreeWidgetItem(dark_root)
                dark_group_item.setText(0, group_name)
                dark_group_item.setText(3, exp_str)  # Exposure column
                dark_group_item.setText(4, temp_str)  # Temp column
                dark_group_item.setText(5, binning)  # Binning column

                # Get dates for this dark group
                cursor.execute('''
                    SELECT DISTINCT date_loc
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Dark%'
                        AND object IS NULL
                        AND (exposure = ? OR (exposure IS NULL AND ? IS NULL))
                        AND (ROUND(ccd_temp) = ? OR (ccd_temp IS NULL AND ? IS NULL))
                        AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                        AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                    ORDER BY date_loc DESC
                ''', (exp, exp, temp, temp, xbin, xbin, ybin, ybin))

                dark_dates = cursor.fetchall()

                for (date_val,) in dark_dates:
                    date_item = QTreeWidgetItem(dark_group_item)
                    date_item.setText(0, date_val or 'No Date')

                    # Get files for this dark group and date
                    cursor.execute('''
                        SELECT filename, imagetyp, exposure, telescop, instrume, date_loc, filter, ccd_temp, xbinning, ybinning
                        FROM xisf_files
                        WHERE imagetyp LIKE '%Dark%'
                            AND object IS NULL
                            AND (exposure = ? OR (exposure IS NULL AND ? IS NULL))
                            AND (ROUND(ccd_temp) = ? OR (ccd_temp IS NULL AND ? IS NULL))
                            AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                            AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                            AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                        ORDER BY filename
                    ''', (exp, exp, temp, temp, xbin, xbin, ybin, ybin, date_val, date_val))

                    dark_files = cursor.fetchall()

                    for filename, imagetyp, exposure, telescop, instrume, date_loc, filt, temp_val, xb, yb in dark_files:
                        file_item = QTreeWidgetItem(date_item)
                        file_item.setText(0, filename)
                        file_item.setText(1, imagetyp or 'N/A')
                        file_item.setText(2, filt or 'N/A')
                        file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
                        file_item.setText(4, f"{temp_val:.1f}°C" if temp_val is not None else 'N/A')
                        binning_str = f"{int(xb)}x{int(yb)}" if xb and yb else 'N/A'
                        file_item.setText(5, binning_str)
                        file_item.setText(6, date_loc or 'N/A')
                        file_item.setText(7, telescop or 'N/A')
                        file_item.setText(8, instrume or 'N/A')

                        # Apply color coding based on image type
                        color = self.get_item_color(imagetyp)
                        if color:
                            for col in range(9):
                                file_item.setBackground(col, QBrush(color))

            # ----- FLAT FRAMES: date → filter_temp_binning → files -----
            cursor.execute('SELECT COUNT(*) FROM xisf_files WHERE imagetyp LIKE "%Flat%" AND object IS NULL')
            flat_count = cursor.fetchone()[0]
            flat_root = QTreeWidgetItem(calib_root)
            flat_root.setText(0, f"Flat Frames ({flat_count} files)")
            flat_root.setFlags(flat_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            cursor.execute('''
                SELECT DISTINCT date_loc
                FROM xisf_files
                WHERE imagetyp LIKE '%Flat%' AND object IS NULL
                ORDER BY date_loc DESC
            ''')

            flat_dates = cursor.fetchall()

            for (date_val,) in flat_dates:
                date_item = QTreeWidgetItem(flat_root)
                date_item.setText(0, date_val or 'No Date')

                # Get filter/temp/binning groups for this date
                cursor.execute('''
                    SELECT
                        filter,
                        ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                        xbinning,
                        ybinning,
                        COUNT(*) as file_count
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Flat%'
                        AND object IS NULL
                        AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                    GROUP BY filter, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning
                    ORDER BY filter, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning
                ''', (date_val, date_val))

                flat_groups = cursor.fetchall()

                for filt, temp, xbin, ybin, count in flat_groups:
                    # Create flat group node (e.g., "Ha_-10C_Bin1x1 (30 files)")
                    filt_str = filt or "NoFilter"
                    temp_str = f"{int(temp)}C" if temp is not None else "0C"
                    binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
                    group_name = f"{filt_str}_{temp_str}_{binning} ({count} files)"

                    flat_group_item = QTreeWidgetItem(date_item)
                    flat_group_item.setText(0, group_name)
                    flat_group_item.setText(2, filt_str)  # Filter column
                    flat_group_item.setText(4, temp_str)  # Temp column
                    flat_group_item.setText(5, binning)  # Binning column

                    # Get files for this flat group
                    cursor.execute('''
                        SELECT filename, imagetyp, exposure, telescop, instrume, date_loc, filter, ccd_temp, xbinning, ybinning
                        FROM xisf_files
                        WHERE imagetyp LIKE '%Flat%'
                            AND object IS NULL
                            AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                            AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                            AND (ROUND(ccd_temp) = ? OR (ccd_temp IS NULL AND ? IS NULL))
                            AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                            AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                        ORDER BY filename
                    ''', (date_val, date_val, filt, filt, temp, temp, xbin, xbin, ybin, ybin))

                    flat_files = cursor.fetchall()

                    for filename, imagetyp, exposure, telescop, instrume, date_loc, filt_val, temp_val, xb, yb in flat_files:
                        file_item = QTreeWidgetItem(flat_group_item)
                        file_item.setText(0, filename)
                        file_item.setText(1, imagetyp or 'N/A')
                        file_item.setText(2, filt_val or 'N/A')
                        file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
                        file_item.setText(4, f"{temp_val:.1f}°C" if temp_val is not None else 'N/A')
                        binning_str = f"{int(xb)}x{int(yb)}" if xb and yb else 'N/A'
                        file_item.setText(5, binning_str)
                        file_item.setText(6, date_loc or 'N/A')
                        file_item.setText(7, telescop or 'N/A')
                        file_item.setText(8, instrume or 'N/A')

                        # Apply color coding based on image type
                        color = self.get_item_color(imagetyp)
                        if color:
                            for col in range(9):
                                file_item.setBackground(col, QBrush(color))

            # ----- BIAS FRAMES: temp_binning → date → files -----
            cursor.execute('SELECT COUNT(*) FROM xisf_files WHERE imagetyp LIKE "%Bias%" AND object IS NULL')
            bias_count = cursor.fetchone()[0]
            bias_root = QTreeWidgetItem(calib_root)
            bias_root.setText(0, f"Bias Frames ({bias_count} files)")
            bias_root.setFlags(bias_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            cursor.execute('''
                SELECT
                    ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                    xbinning,
                    ybinning,
                    COUNT(*) as file_count
                FROM xisf_files
                WHERE imagetyp LIKE '%Bias%' AND object IS NULL
                GROUP BY ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning
                ORDER BY ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning
            ''')

            bias_groups = cursor.fetchall()

            for temp, xbin, ybin, count in bias_groups:
                # Create bias group node (e.g., "-10C_Bin1x1 (50 files)")
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
                group_name = f"{temp_str}_{binning} ({count} files)"

                bias_group_item = QTreeWidgetItem(bias_root)
                bias_group_item.setText(0, group_name)
                bias_group_item.setText(4, temp_str)  # Temp column
                bias_group_item.setText(5, binning)  # Binning column

                # Get dates for this bias group
                cursor.execute('''
                    SELECT DISTINCT date_loc
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Bias%'
                        AND object IS NULL
                        AND (ROUND(ccd_temp) = ? OR (ccd_temp IS NULL AND ? IS NULL))
                        AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                        AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                    ORDER BY date_loc DESC
                ''', (temp, temp, xbin, xbin, ybin, ybin))

                bias_dates = cursor.fetchall()

                for (date_val,) in bias_dates:
                    date_item = QTreeWidgetItem(bias_group_item)
                    date_item.setText(0, date_val or 'No Date')

                    # Get files for this bias group and date
                    cursor.execute('''
                        SELECT filename, imagetyp, exposure, telescop, instrume, date_loc, filter, ccd_temp, xbinning, ybinning
                        FROM xisf_files
                        WHERE imagetyp LIKE '%Bias%'
                            AND object IS NULL
                            AND (ROUND(ccd_temp) = ? OR (ccd_temp IS NULL AND ? IS NULL))
                            AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                            AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                            AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                        ORDER BY filename
                    ''', (temp, temp, xbin, xbin, ybin, ybin, date_val, date_val))

                    bias_files = cursor.fetchall()

                    for filename, imagetyp, exposure, telescop, instrume, date_loc, filt, temp_val, xb, yb in bias_files:
                        file_item = QTreeWidgetItem(date_item)
                        file_item.setText(0, filename)
                        file_item.setText(1, imagetyp or 'N/A')
                        file_item.setText(2, filt or 'N/A')
                        file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
                        file_item.setText(4, f"{temp_val:.1f}°C" if temp_val is not None else 'N/A')
                        binning_str = f"{int(xb)}x{int(yb)}" if xb and yb else 'N/A'
                        file_item.setText(5, binning_str)
                        file_item.setText(6, date_loc or 'N/A')
                        file_item.setText(7, telescop or 'N/A')
                        file_item.setText(8, instrume or 'N/A')

                        # Apply color coding based on image type
                        color = self.get_item_color(imagetyp)
                        if color:
                            for col in range(9):
                                file_item.setBackground(col, QBrush(color))

            conn.close()

            # Don't expand any items by default - keep everything collapsed

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh view: {e}')
    
    def on_tab_changed(self, index):
        """Handle tab change"""
        if index == 0:  # View Catalog tab
            self.refresh_catalog_view()
        elif index == 1:  # Sessions tab
            self.refresh_sessions()
        elif index == 2:  # Analytics tab
            self.refresh_analytics()
        elif index == 4:  # Maintenance tab
            # Populate current values when maintenance tab is opened
            keyword = self.keyword_combo.currentText()
            self.populate_current_values(keyword)

    def refresh_sessions(self):
        """Refresh the sessions view"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            self.sessions_tree.clear()

            # Find all unique sessions (date + object + filter combination for light frames)
            cursor.execute('''
                SELECT
                    date_loc,
                    object,
                    filter,
                    COUNT(*) as frame_count,
                    AVG(exposure) as avg_exposure,
                    AVG(ccd_temp) as avg_temp,
                    xbinning,
                    ybinning
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
                    AND object IS NOT NULL
                GROUP BY date_loc, object, filter
                ORDER BY date_loc DESC, object, filter
            ''')

            sessions = cursor.fetchall()

            # Statistics counters
            total_count = 0
            complete_count = 0
            partial_count = 0
            missing_count = 0

            for session_data in sessions:
                date, obj, filt, frame_count, avg_exp, avg_temp, xbin, ybin = session_data

                # Find matching calibration frames
                darks_info = self.find_matching_darks(cursor, avg_exp, avg_temp, xbin, ybin)
                bias_info = self.find_matching_bias(cursor, avg_temp, xbin, ybin)
                flats_info = self.find_matching_flats(cursor, filt, avg_temp, xbin, ybin, date)

                # Calculate session status
                status, status_color = self.calculate_session_status(darks_info, bias_info, flats_info)

                # Apply filters
                status_filter = self.session_status_filter.currentText()
                if status_filter != 'All' and status != status_filter:
                    continue

                if self.missing_only_checkbox.isChecked() and status != 'Missing':
                    continue

                # Update statistics
                total_count += 1
                if status == 'Complete':
                    complete_count += 1
                elif status == 'Partial':
                    partial_count += 1
                elif status == 'Missing':
                    missing_count += 1

                # Create session tree item
                session_name = f"{date} - {obj} - {filt or 'No Filter'}"
                session_item = QTreeWidgetItem(self.sessions_tree)
                session_item.setText(0, session_name)
                session_item.setText(1, status)
                session_item.setText(2, f"{frame_count} frames")
                session_item.setText(3, darks_info['display'])
                session_item.setText(4, bias_info['display'])
                session_item.setText(5, flats_info['display'])

                # Set status color
                for col in range(6):
                    session_item.setForeground(col, status_color)

                # Store session data for details view
                session_item.setData(0, Qt.ItemDataRole.UserRole, {
                    'date': date,
                    'object': obj,
                    'filter': filt,
                    'frame_count': frame_count,
                    'avg_exposure': avg_exp,
                    'avg_temp': avg_temp,
                    'xbinning': xbin,
                    'ybinning': ybin,
                    'darks': darks_info,
                    'bias': bias_info,
                    'flats': flats_info,
                    'status': status
                })

            conn.close()

            # Update statistics panel
            self.update_session_statistics(total_count, complete_count, partial_count, missing_count)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh sessions: {e}')

    def find_matching_darks(self, cursor, exposure, temp, xbin, ybin):
        """Find matching dark frames with temperature tolerance (delegates to CalibrationMatcher)"""
        # Update include_masters from checkbox state
        self.calibration.include_masters = self.include_masters_checkbox.isChecked()
        # Delegate to CalibrationMatcher
        return self.calibration.find_matching_darks(exposure, temp, xbin, ybin)

    def find_matching_bias(self, cursor, temp, xbin, ybin):
        """Find matching bias frames with temperature tolerance (delegates to CalibrationMatcher)"""
        # Update include_masters from checkbox state
        self.calibration.include_masters = self.include_masters_checkbox.isChecked()
        # Delegate to CalibrationMatcher
        return self.calibration.find_matching_bias(temp, xbin, ybin)

    def find_matching_flats(self, cursor, filter_name, temp, xbin, ybin, session_date):
        """Find matching flat frames with temperature tolerance and exact date match (delegates to CalibrationMatcher)"""
        # Update include_masters from checkbox state
        self.calibration.include_masters = self.include_masters_checkbox.isChecked()
        # Delegate to CalibrationMatcher
        return self.calibration.find_matching_flats(filter_name, temp, xbin, ybin, session_date)

    def calculate_session_status(self, darks_info, bias_info, flats_info):
        """Calculate overall session status (delegates to CalibrationMatcher)"""
        return self.calibration.calculate_session_status(darks_info, bias_info, flats_info)

    def on_session_clicked(self, item, column):
        """Handle session tree item click"""
        session_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not session_data:
            return

        # Display session details
        details = []
        details.append(f"<h3>Session: {session_data['date']} - {session_data['object']}</h3>")
        details.append(f"<b>Filter:</b> {session_data['filter'] or 'None'}<br>")
        details.append(f"<b>Light Frames:</b> {session_data['frame_count']}<br>")
        details.append(f"<b>Average Exposure:</b> {session_data['avg_exposure']:.1f}s<br>")
        details.append(f"<b>Average Temperature:</b> {session_data['avg_temp']:.1f}°C<br>")
        details.append(f"<b>Binning:</b> {session_data['xbinning']}x{session_data['ybinning']}<br>")
        details.append(f"<b>Status:</b> {session_data['status']}<br>")

        details.append("<h4>Calibration Frames:</h4>")

        darks = session_data['darks']
        details.append(f"<b>Darks ({darks['exposure']:.1f}s):</b> {darks['count']} frames")
        if darks['master_count'] > 0:
            details.append(f" + {darks['master_count']} master(s)")
        details.append(f" (Quality: {darks['quality']:.0f}%)<br>")

        bias = session_data['bias']
        details.append(f"<b>Bias:</b> {bias['count']} frames")
        if bias['master_count'] > 0:
            details.append(f" + {bias['master_count']} master(s)")
        details.append(f" (Quality: {bias['quality']:.0f}%)<br>")

        flats = session_data['flats']
        details.append(f"<b>Flats ({flats['filter'] or 'No Filter'}):</b> {flats['count']} frames")
        if flats['master_count'] > 0:
            details.append(f" + {flats['master_count']} master(s)")
        details.append(f" (Quality: {flats['quality']:.0f}%)<br>")

        self.session_details_text.setHtml(''.join(details))

        # Generate recommendations
        recommendations = self.generate_recommendations(session_data)
        self.recommendations_text.setPlainText(recommendations)

    def generate_recommendations(self, session_data):
        """Generate recommendations for missing or incomplete calibration frames (delegates to CalibrationMatcher)"""
        return self.calibration.generate_recommendations(session_data)

    def update_session_statistics(self, total, complete, partial, missing):
        """Update the session statistics panel"""
        self.total_sessions_label.setText(f'Total Sessions: {total}')
        self.complete_sessions_label.setText(f'Complete: {complete}')
        self.partial_sessions_label.setText(f'Partial: {partial}')
        self.missing_sessions_label.setText(f'Missing: {missing}')

        if total > 0:
            completion_rate = (complete / total) * 100
            self.completion_rate_label.setText(f'Completion Rate: {completion_rate:.1f}%')
        else:
            self.completion_rate_label.setText('Completion Rate: 0%')

    def export_session_report(self):
        """Export session report to text file"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                'Export Session Report',
                'session_report.txt',
                'Text Files (*.txt);;All Files (*)'
            )

            if not filename:
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all sessions
            cursor.execute('''
                SELECT
                    date_loc,
                    object,
                    filter,
                    COUNT(*) as frame_count,
                    AVG(exposure) as avg_exposure,
                    AVG(ccd_temp) as avg_temp,
                    xbinning,
                    ybinning
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
                    AND object IS NOT NULL
                GROUP BY date_loc, object, filter
                ORDER BY date_loc DESC, object, filter
            ''')

            sessions = cursor.fetchall()

            with open(filename, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("XISF FILE MANAGER - SESSION CALIBRATION REPORT\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Sessions: {len(sessions)}\n\n")

                complete_count = 0
                partial_count = 0
                missing_count = 0

                for session_data in sessions:
                    date, obj, filt, frame_count, avg_exp, avg_temp, xbin, ybin = session_data

                    # Find matching calibration frames
                    darks_info = self.find_matching_darks(cursor, avg_exp, avg_temp, xbin, ybin)
                    bias_info = self.find_matching_bias(cursor, avg_temp, xbin, ybin)
                    flats_info = self.find_matching_flats(cursor, filt, avg_temp, xbin, ybin, date)

                    status, _ = self.calculate_session_status(darks_info, bias_info, flats_info)

                    if status == 'Complete':
                        complete_count += 1
                    elif status == 'Partial':
                        partial_count += 1
                    else:
                        missing_count += 1

                    f.write("-" * 80 + "\n")
                    f.write(f"Session: {date} - {obj} - {filt or 'No Filter'}\n")
                    f.write(f"Status: {status}\n")
                    f.write(f"Light Frames: {frame_count} | Exposure: {avg_exp:.1f}s | Temp: {avg_temp:.1f}°C | Binning: {xbin}x{ybin}\n\n")

                    f.write(f"  Darks ({avg_exp:.1f}s): {darks_info['count']} frames")
                    if darks_info['master_count'] > 0:
                        f.write(f" + {darks_info['master_count']} master(s)")
                    f.write(f" (Quality: {darks_info['quality']:.0f}%)\n")

                    f.write(f"  Bias: {bias_info['count']} frames")
                    if bias_info['master_count'] > 0:
                        f.write(f" + {bias_info['master_count']} master(s)")
                    f.write(f" (Quality: {bias_info['quality']:.0f}%)\n")

                    f.write(f"  Flats ({filt or 'No Filter'}): {flats_info['count']} frames")
                    if flats_info['master_count'] > 0:
                        f.write(f" + {flats_info['master_count']} master(s)")
                    f.write(f" (Quality: {flats_info['quality']:.0f}%)\n")

                    # Add recommendations if needed
                    session_dict = {
                        'avg_exposure': avg_exp,
                        'avg_temp': avg_temp,
                        'xbinning': xbin,
                        'ybinning': ybin,
                        'filter': filt,
                        'darks': darks_info,
                        'bias': bias_info,
                        'flats': flats_info
                    }
                    recommendations = self.generate_recommendations(session_dict)
                    if recommendations and not recommendations.startswith('✓ All'):
                        f.write(f"\n  Recommendations:\n")
                        for line in recommendations.split('\n'):
                            if line.strip():
                                f.write(f"    {line}\n")

                    f.write("\n")

                # Summary
                f.write("=" * 80 + "\n")
                f.write("SUMMARY\n")
                f.write("=" * 80 + "\n")
                f.write(f"Total Sessions: {len(sessions)}\n")
                f.write(f"Complete: {complete_count}\n")
                f.write(f"Partial: {partial_count}\n")
                f.write(f"Missing Calibration: {missing_count}\n")
                if len(sessions) > 0:
                    completion_rate = (complete_count / len(sessions)) * 100
                    f.write(f"Completion Rate: {completion_rate:.1f}%\n")

            conn.close()

            QMessageBox.information(
                self,
                'Export Complete',
                f'Session report exported to:\n{filename}'
            )

        except Exception as e:
            QMessageBox.critical(self, 'Export Error', f'Failed to export report: {e}')


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
