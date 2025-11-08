#!/usr/bin/env python3
"""
PyQt GUI for XISF Catalog Database
"""

import sys
import os
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QProgressBar, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QRadioButton, QButtonGroup, QGroupBox, QComboBox,
    QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
import xisf


class ImportWorker(QThread):
    """Worker thread for importing XISF files"""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(int, int)  # processed, errors
    
    def __init__(self, files, db_path):
        super().__init__()
        self.files = files
        self.db_path = db_path
        self.processed = 0
        self.errors = 0
    
    def calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        hash_obj = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    
    def process_date_loc(self, date_str):
        """Process DATE-LOC: subtract 12 hours and return date only in YYYY-MM-DD format"""
        if not date_str:
            return None
        
        try:
            # Convert to string if needed
            date_str = str(date_str).strip()
            
            # Handle fractional seconds that have too many digits (7+ digits instead of 6)
            # Python's %f expects exactly 6 digits for microseconds
            if 'T' in date_str and '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 2:
                    # Truncate fractional seconds to 6 digits
                    fractional = parts[1][:6]
                    date_str = f"{parts[0]}.{fractional}"
            
            # Try parsing common FITS date formats
            formats = [
                '%Y-%m-%dT%H:%M:%S.%f',  # With microseconds
                '%Y-%m-%dT%H:%M:%S',     # Standard ISO format
                '%Y-%m-%d %H:%M:%S',     # Space instead of T
                '%Y-%m-%d',              # Date only
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Subtract 12 hours
                    dt = dt - timedelta(hours=12)
                    result = dt.strftime('%Y-%m-%d')
                    return result
                except ValueError:
                    continue
            
            return None
            
        except Exception:
            return None
    
    def read_fits_keywords(self, filename):
        """Read FITS keywords from XISF file"""
        keywords = ['TELESCOP', 'INSTRUME', 'OBJECT', 'FILTER', 'IMAGETYP',
                    'EXPOSURE', 'EXPTIME', 'CCD-TEMP', 'XBINNING', 'YBINNING', 'DATE-LOC']
        try:
            xisf_file = xisf.XISF(filename)
            im_data = xisf_file.read_image(0)

            if hasattr(xisf_file, 'fits_keywords'):
                fits_keywords = xisf_file.fits_keywords
            elif hasattr(im_data, 'fits_keywords'):
                fits_keywords = im_data.fits_keywords
            else:
                metadata = xisf_file.get_images_metadata()[0]
                fits_keywords = metadata.get('FITSKeywords', {})

            results = {}
            for keyword in keywords:
                if fits_keywords and keyword in fits_keywords:
                    keyword_data = fits_keywords[keyword]
                    if isinstance(keyword_data, list) and len(keyword_data) > 0:
                        results[keyword] = keyword_data[0]['value']
                    else:
                        results[keyword] = keyword_data
                else:
                    results[keyword] = None

            # Special handling: prefer EXPTIME over EXPOSURE (EXPTIME is FITS standard)
            # This ensures compatibility with both standard and non-standard keywords
            if results.get('EXPTIME') is not None:
                results['EXPOSURE'] = results['EXPTIME']

            return results
        except Exception as e:
            return None
    
    def run(self):
        """Process files and import to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Use batch processing for better performance
        batch_size = 50
        batch_data = []
        
        for i, filepath in enumerate(self.files):
            basename = os.path.basename(filepath)
            self.progress.emit(i + 1, len(self.files), f"Processing: {basename}")
            
            try:
                # Calculate hash
                file_hash = self.calculate_file_hash(filepath)
                
                # Read FITS keywords
                keywords = self.read_fits_keywords(filepath)
                
                if keywords:
                    filename = os.path.basename(filepath)

                    # Process DATE-LOC to subtract 12 hours and get date only
                    date_loc = self.process_date_loc(keywords.get('DATE-LOC'))

                    # Determine if this is a calibration frame
                    imagetyp = keywords.get('IMAGETYP', '')
                    is_calibration = False
                    if imagetyp:
                        imagetyp_lower = imagetyp.lower()
                        is_calibration = ('dark' in imagetyp_lower or
                                        'flat' in imagetyp_lower or
                                        'bias' in imagetyp_lower)

                    # Set object to None for calibration frames (they are not object-specific)
                    obj = None if is_calibration else keywords.get('OBJECT')

                    # Add to batch
                    batch_data.append((
                        file_hash, filepath, filename,
                        keywords.get('TELESCOP'), keywords.get('INSTRUME'),
                        obj, keywords.get('FILTER'),
                        keywords.get('IMAGETYP'), keywords.get('EXPOSURE'),
                        keywords.get('CCD-TEMP'), keywords.get('XBINNING'),
                        keywords.get('YBINNING'), date_loc
                    ))
                    
                    # Process batch when it reaches batch_size or on last file
                    if len(batch_data) >= batch_size or i == len(self.files) - 1:
                        # Insert batch using executemany for better performance
                        cursor.execute('BEGIN TRANSACTION')
                        
                        for data in batch_data:
                            file_hash = data[0]
                            
                            # Check if exists
                            cursor.execute('SELECT id FROM xisf_files WHERE file_hash = ?', (file_hash,))
                            existing = cursor.fetchone()
                            
                            if existing:
                                cursor.execute('''
                                    UPDATE xisf_files
                                    SET filepath = ?, filename = ?, telescop = ?, instrume = ?, 
                                        object = ?, filter = ?, imagetyp = ?, exposure = ?,
                                        ccd_temp = ?, xbinning = ?, ybinning = ?, date_loc = ?,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE file_hash = ?
                                ''', data[1:] + (file_hash,))
                            else:
                                cursor.execute('''
                                    INSERT INTO xisf_files 
                                    (file_hash, filepath, filename, telescop, instrume, object, 
                                     filter, imagetyp, exposure, ccd_temp, xbinning, ybinning, date_loc)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', data)
                        
                        conn.commit()
                        self.processed += len(batch_data)
                        batch_data = []
                else:
                    self.errors += 1
                    
            except Exception as e:
                self.errors += 1
        
        conn.close()
        self.finished.emit(self.processed, self.errors)


class XISFCatalogGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = 'xisf_catalog.db'
        self.settings = QSettings('XISFCatalog', 'CatalogGUI')
        self.init_ui()
        # Restore settings after all UI is created
        self.restore_settings()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('XISF Catalog Manager')
        self.setGeometry(100, 100, 1000, 600)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Create tabs
        self.import_tab = self.create_import_tab()
        self.view_tab = self.create_view_tab()
        self.analytics_tab = self.create_analytics_tab()
        self.maintenance_tab = self.create_maintenance_tab()
        self.settings_tab = self.create_settings_tab()

        tabs.addTab(self.import_tab, "Import Files")
        tabs.addTab(self.view_tab, "View Catalog")
        tabs.addTab(self.analytics_tab, "Analytics")
        tabs.addTab(self.maintenance_tab, "Maintenance")
        tabs.addTab(self.settings_tab, "Settings")
        
        # Connect tab change to refresh
        tabs.currentChanged.connect(self.on_tab_changed)
    
    def create_import_tab(self):
        """Create the import tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Database info
        db_label = QLabel(f"Database: {self.db_path}")
        layout.addWidget(db_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.import_files_btn = QPushButton('Import XISF Files')
        self.import_files_btn.clicked.connect(self.import_files)
        button_layout.addWidget(self.import_files_btn)
        
        self.import_folder_btn = QPushButton('Import Folder')
        self.import_folder_btn.clicked.connect(self.import_folder)
        button_layout.addWidget(self.import_folder_btn)
        
        layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel('')
        layout.addWidget(self.status_label)
        
        # Log area
        log_label = QLabel('Import Log:')
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
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

        # Fix Calibration Frame Objects section
        fix_calib_group = QGroupBox("Fix Calibration Data")
        fix_calib_layout = QVBoxLayout()

        fix_calib_info = QLabel("Remove object field from calibration frames (Dark, Flat, Bias):")
        fix_calib_layout.addWidget(fix_calib_info)

        fix_calib_help = QLabel("Some flat/dark/bias frames may have been imported with an object field.\n"
                               "This tool removes the object field from all calibration frames.")
        fix_calib_help.setStyleSheet("color: #888888; font-size: 10px;")
        fix_calib_layout.addWidget(fix_calib_help)

        self.fix_calib_btn = QPushButton('Fix Calibration Frame Objects')
        self.fix_calib_btn.clicked.connect(self.fix_calibration_objects)
        fix_calib_layout.addWidget(self.fix_calib_btn)

        fix_calib_group.setLayout(fix_calib_layout)
        layout.addWidget(fix_calib_group)

        # Re-extract Exposure Times section
        reextract_group = QGroupBox("Re-extract Exposure Times")
        reextract_layout = QVBoxLayout()

        reextract_info = QLabel("Re-read exposure times from files using EXPTIME keyword:")
        reextract_layout.addWidget(reextract_info)

        reextract_help = QLabel("Some files may have been imported with NULL exposure because they use\n"
                               "EXPTIME instead of EXPOSURE. This tool re-reads exposure data from the files.")
        reextract_help.setStyleSheet("color: #888888; font-size: 10px;")
        reextract_layout.addWidget(reextract_help)

        self.reextract_btn = QPushButton('Re-extract Exposure Times')
        self.reextract_btn.clicked.connect(self.reextract_exposure_times)
        reextract_layout.addWidget(self.reextract_btn)

        reextract_group.setLayout(reextract_layout)
        layout.addWidget(reextract_group)

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

    def fix_calibration_objects(self):
        """Remove object field from calibration frames"""
        reply = QMessageBox.question(
            self, 'Fix Calibration Frame Objects',
            'This will remove the object field from all Dark, Flat, and Bias frames.\n\n'
            'Calibration frames should not have an object associated with them.\n\n'
            'Continue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE xisf_files
                SET object = NULL
                WHERE (imagetyp LIKE '%Dark%'
                    OR imagetyp LIKE '%Flat%'
                    OR imagetyp LIKE '%Bias%')
                    AND object IS NOT NULL
            ''')

            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            QMessageBox.information(
                self, 'Success',
                f'Fixed {rows_affected} calibration frame(s).\n\n'
                'Object field has been removed from Dark, Flat, and Bias frames.'
            )

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to fix calibration frames: {e}')

    def reextract_exposure_times(self):
        """Re-read exposure times from files that have NULL exposure"""
        reply = QMessageBox.question(
            self, 'Re-extract Exposure Times',
            'This will re-read FITS keywords from files with NULL exposure.\n\n'
            'Files with EXPTIME keyword will have their exposure time updated.\n\n'
            'This may take some time if you have many files. Continue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all files with NULL exposure
            cursor.execute('''
                SELECT id, filepath
                FROM xisf_files
                WHERE exposure IS NULL
            ''')

            files_to_update = cursor.fetchall()

            if not files_to_update:
                QMessageBox.information(
                    self, 'No Files to Update',
                    'No files with NULL exposure found.'
                )
                conn.close()
                return

            updated_count = 0
            error_count = 0

            # Re-read FITS keywords from each file
            for file_id, filepath in files_to_update:
                try:
                    if not os.path.exists(filepath):
                        error_count += 1
                        continue

                    # Use the ImportWorker's read_fits_keywords method
                    worker = ImportWorker([], self.db_path)
                    keywords = worker.read_fits_keywords(filepath)

                    if keywords and keywords.get('EXPOSURE') is not None:
                        cursor.execute('''
                            UPDATE xisf_files
                            SET exposure = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (keywords.get('EXPOSURE'), file_id))
                        updated_count += 1

                except Exception:
                    error_count += 1

            conn.commit()
            conn.close()

            QMessageBox.information(
                self, 'Success',
                f'Re-extracted exposure times from {updated_count} file(s).\n'
                f'Errors: {error_count}\n\n'
                'Files with EXPTIME keyword now have their exposure time populated.'
            )

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to re-extract exposure times: {e}')

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
                new_path = self.generate_organized_path(
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
                    new_path = self.generate_organized_path(
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
    
    def generate_organized_path(self, repo_path, obj, filt, imgtyp, exp, temp, xbin, ybin, date, original_filename):
        """Generate the organized path and filename for a file"""
        # Sanitize values
        obj = obj or "Unknown"
        filt = filt or "NoFilter"
        imgtyp = imgtyp or "Unknown"
        date = date or "0000-00-00"
        
        # Determine binning string
        if xbin and ybin:
            binning = f"Bin{int(xbin)}x{int(ybin)}"
        else:
            binning = "Bin1x1"
        
        # Determine temp string
        temp_str = f"{int(temp)}C" if temp is not None else "0C"
        
        # Extract sequence number from original filename if possible
        import re
        seq_match = re.search(r'_(\d+)\.(xisf|fits?)$', original_filename, re.IGNORECASE)
        seq = seq_match.group(1) if seq_match else "001"
        
        # Determine file type and path structure
        if 'light' in imgtyp.lower():
            # Lights/[Object]/[Filter]/[filename]
            subdir = os.path.join("Lights", obj, filt)
            exp_str = f"{int(exp)}s" if exp else "0s"
            new_filename = f"{date}_{obj}_{filt}_{exp_str}_{temp_str}_{binning}_{seq}.xisf"
            
        elif 'dark' in imgtyp.lower():
            # Calibration/Darks/[exp]_[temp]_[binning]/[filename]
            exp_str = f"{int(exp)}s" if exp else "0s"
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
    
    def save_settings(self):
        """Save window size and column widths"""
        # Save window geometry
        self.settings.setValue('geometry', self.saveGeometry())

        # Save catalog tree column widths
        for i in range(self.catalog_tree.columnCount()):
            self.settings.setValue(f'catalog_tree_col_{i}', self.catalog_tree.columnWidth(i))
    
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
        
        # Refresh button
        refresh_btn = QPushButton('Refresh')
        refresh_btn.clicked.connect(self.refresh_catalog_view)
        layout.addWidget(refresh_btn)
        
        # Tree widget
        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setColumnCount(4)
        self.catalog_tree.setHeaderLabels([
            'Name', 'Image Type', 'Telescope', 'Instrument'
        ])
        self.catalog_tree.setColumnWidth(0, 300)
        layout.addWidget(self.catalog_tree)
        
        return widget
    
    def import_files(self):
        """Import individual XISF files"""
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Select XISF Files', '', 'XISF Files (*.xisf)'
        )
        
        if files:
            self.start_import(files)
    
    def import_folder(self):
        """Import all XISF files from a folder and its subfolders"""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        
        if folder:
            # Recursively find all .xisf files in folder and subfolders
            files = list(Path(folder).rglob('*.xisf'))
            if files:
                self.start_import([str(f) for f in files])
            else:
                QMessageBox.warning(self, 'No Files', 'No XISF files found in selected folder or its subfolders.')
    
    def start_import(self, files):
        """Start the import worker thread"""
        if not os.path.exists(self.db_path):
            QMessageBox.critical(
                self, 'Database Error',
                f'Database not found: {self.db_path}\nPlease create it first.'
            )
            return
        
        self.log_text.clear()
        self.log_text.append(f"Starting import of {len(files)} files...\n")
        
        # Disable buttons
        self.import_files_btn.setEnabled(False)
        self.import_folder_btn.setEnabled(False)
        self.clear_db_btn.setEnabled(False)
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setValue(0)
        
        # Create and start worker
        self.worker = ImportWorker(files, self.db_path)
        self.worker.progress.connect(self.on_import_progress)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.start()
    
    def on_import_progress(self, current, total, message):
        """Handle progress updates"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing {current}/{total}")
        self.log_text.append(message)
    
    def on_import_finished(self, processed, errors):
        """Handle import completion"""
        self.progress_bar.setVisible(False)
        self.status_label.setText('')
        
        self.log_text.append(f"\n{'='*60}")
        self.log_text.append(f"Import complete!")
        self.log_text.append(f"Successfully processed: {processed}")
        self.log_text.append(f"Errors: {errors}")
        
        # Re-enable buttons
        self.import_files_btn.setEnabled(True)
        self.import_folder_btn.setEnabled(True)
        self.clear_db_btn.setEnabled(True)
        
        QMessageBox.information(
            self, 'Import Complete',
            f'Successfully processed: {processed}\nErrors: {errors}'
        )
    
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
    
    def refresh_catalog_view(self):
        """Refresh the catalog view tree"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            self.catalog_tree.clear()

            # ===== LIGHT FRAMES SECTION =====
            light_frames_root = QTreeWidgetItem(self.catalog_tree)
            light_frames_root.setText(0, "Light Frames")
            light_frames_root.setFlags(light_frames_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            # Get all objects (light frames only)
            cursor.execute('''
                SELECT
                    object,
                    COUNT(*) as file_count,
                    SUM(exposure) as total_exposure
                FROM xisf_files
                WHERE object IS NOT NULL
                GROUP BY object
                ORDER BY object
            ''')

            objects = cursor.fetchall()

            for obj_name, obj_file_count, obj_total_exp in objects:
                # Create object node
                obj_item = QTreeWidgetItem(light_frames_root)
                obj_item.setText(0, obj_name or 'Unknown')
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
                    # Create filter node
                    filter_item = QTreeWidgetItem(obj_item)
                    filter_item.setText(0, filter_name or 'No Filter')

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
                        # Create date node
                        date_item = QTreeWidgetItem(filter_item)
                        date_item.setText(0, date_val or 'No Date')

                        # Get all files for this object, filter, and date
                        cursor.execute('''
                            SELECT
                                filename,
                                imagetyp,
                                exposure,
                                telescop,
                                instrume,
                                date_loc
                            FROM xisf_files
                            WHERE object = ?
                                AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                                AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                            ORDER BY filename
                        ''', (obj_name, filter_name, filter_name, date_val, date_val))

                        files = cursor.fetchall()

                        for filename, imagetyp, exposure, telescop, instrume, date_loc in files:
                            # Create file node
                            file_item = QTreeWidgetItem(date_item)
                            file_item.setText(0, filename)
                            file_item.setText(1, imagetyp or 'N/A')
                            file_item.setText(2, telescop or 'N/A')
                            file_item.setText(3, instrume or 'N/A')

            # ===== CALIBRATION FRAMES SECTION =====
            calib_root = QTreeWidgetItem(self.catalog_tree)
            calib_root.setText(0, "Calibration Frames")
            calib_root.setFlags(calib_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            # ----- DARK FRAMES: exposure_temp_binning → date → files -----
            dark_root = QTreeWidgetItem(calib_root)
            dark_root.setText(0, "Dark Frames")
            dark_root.setFlags(dark_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            cursor.execute('''
                SELECT
                    exposure,
                    ccd_temp,
                    xbinning,
                    ybinning,
                    COUNT(*) as file_count
                FROM xisf_files
                WHERE imagetyp LIKE '%Dark%' AND object IS NULL
                GROUP BY exposure, ccd_temp, xbinning, ybinning
                ORDER BY exposure, ccd_temp, xbinning, ybinning
            ''')

            dark_groups = cursor.fetchall()

            for exp, temp, xbin, ybin, count in dark_groups:
                # Create dark group node (e.g., "300s_-10C_Bin1x1")
                exp_str = f"{int(exp)}s" if exp else "0s"
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
                group_name = f"{exp_str}_{temp_str}_{binning}"

                dark_group_item = QTreeWidgetItem(dark_root)
                dark_group_item.setText(0, group_name)

                # Get dates for this dark group
                cursor.execute('''
                    SELECT DISTINCT date_loc
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Dark%'
                        AND object IS NULL
                        AND (exposure = ? OR (exposure IS NULL AND ? IS NULL))
                        AND (ccd_temp = ? OR (ccd_temp IS NULL AND ? IS NULL))
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
                        SELECT filename, imagetyp, exposure, telescop, instrume
                        FROM xisf_files
                        WHERE imagetyp LIKE '%Dark%'
                            AND object IS NULL
                            AND (exposure = ? OR (exposure IS NULL AND ? IS NULL))
                            AND (ccd_temp = ? OR (ccd_temp IS NULL AND ? IS NULL))
                            AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                            AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                            AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                        ORDER BY filename
                    ''', (exp, exp, temp, temp, xbin, xbin, ybin, ybin, date_val, date_val))

                    dark_files = cursor.fetchall()

                    for filename, imagetyp, exposure, telescop, instrume in dark_files:
                        file_item = QTreeWidgetItem(date_item)
                        file_item.setText(0, filename)
                        file_item.setText(1, imagetyp or 'N/A')
                        file_item.setText(2, telescop or 'N/A')
                        file_item.setText(3, instrume or 'N/A')

            # ----- FLAT FRAMES: date → filter_temp_binning → files -----
            flat_root = QTreeWidgetItem(calib_root)
            flat_root.setText(0, "Flat Frames")
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
                        ccd_temp,
                        xbinning,
                        ybinning,
                        COUNT(*) as file_count
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Flat%'
                        AND object IS NULL
                        AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                    GROUP BY filter, ccd_temp, xbinning, ybinning
                    ORDER BY filter, ccd_temp, xbinning, ybinning
                ''', (date_val, date_val))

                flat_groups = cursor.fetchall()

                for filt, temp, xbin, ybin, count in flat_groups:
                    # Create flat group node (e.g., "Ha_-10C_Bin1x1")
                    filt_str = filt or "NoFilter"
                    temp_str = f"{int(temp)}C" if temp is not None else "0C"
                    binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
                    group_name = f"{filt_str}_{temp_str}_{binning}"

                    flat_group_item = QTreeWidgetItem(date_item)
                    flat_group_item.setText(0, group_name)

                    # Get files for this flat group
                    cursor.execute('''
                        SELECT filename, imagetyp, exposure, telescop, instrume
                        FROM xisf_files
                        WHERE imagetyp LIKE '%Flat%'
                            AND object IS NULL
                            AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                            AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                            AND (ccd_temp = ? OR (ccd_temp IS NULL AND ? IS NULL))
                            AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                            AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                        ORDER BY filename
                    ''', (date_val, date_val, filt, filt, temp, temp, xbin, xbin, ybin, ybin))

                    flat_files = cursor.fetchall()

                    for filename, imagetyp, exposure, telescop, instrume in flat_files:
                        file_item = QTreeWidgetItem(flat_group_item)
                        file_item.setText(0, filename)
                        file_item.setText(1, imagetyp or 'N/A')
                        file_item.setText(2, telescop or 'N/A')
                        file_item.setText(3, instrume or 'N/A')

            # ----- BIAS FRAMES: temp_binning → date → files -----
            bias_root = QTreeWidgetItem(calib_root)
            bias_root.setText(0, "Bias Frames")
            bias_root.setFlags(bias_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

            cursor.execute('''
                SELECT
                    ccd_temp,
                    xbinning,
                    ybinning,
                    COUNT(*) as file_count
                FROM xisf_files
                WHERE imagetyp LIKE '%Bias%' AND object IS NULL
                GROUP BY ccd_temp, xbinning, ybinning
                ORDER BY ccd_temp, xbinning, ybinning
            ''')

            bias_groups = cursor.fetchall()

            for temp, xbin, ybin, count in bias_groups:
                # Create bias group node (e.g., "-10C_Bin1x1")
                temp_str = f"{int(temp)}C" if temp is not None else "0C"
                binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"
                group_name = f"{temp_str}_{binning}"

                bias_group_item = QTreeWidgetItem(bias_root)
                bias_group_item.setText(0, group_name)

                # Get dates for this bias group
                cursor.execute('''
                    SELECT DISTINCT date_loc
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Bias%'
                        AND object IS NULL
                        AND (ccd_temp = ? OR (ccd_temp IS NULL AND ? IS NULL))
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
                        SELECT filename, imagetyp, exposure, telescop, instrume
                        FROM xisf_files
                        WHERE imagetyp LIKE '%Bias%'
                            AND object IS NULL
                            AND (ccd_temp = ? OR (ccd_temp IS NULL AND ? IS NULL))
                            AND (xbinning = ? OR (xbinning IS NULL AND ? IS NULL))
                            AND (ybinning = ? OR (ybinning IS NULL AND ? IS NULL))
                            AND (date_loc = ? OR (date_loc IS NULL AND ? IS NULL))
                        ORDER BY filename
                    ''', (temp, temp, xbin, xbin, ybin, ybin, date_val, date_val))

                    bias_files = cursor.fetchall()

                    for filename, imagetyp, exposure, telescop, instrume in bias_files:
                        file_item = QTreeWidgetItem(date_item)
                        file_item.setText(0, filename)
                        file_item.setText(1, imagetyp or 'N/A')
                        file_item.setText(2, telescop or 'N/A')
                        file_item.setText(3, instrume or 'N/A')

            conn.close()

            # Don't expand any items by default - keep everything collapsed

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh view: {e}')
    
    def on_tab_changed(self, index):
        """Handle tab change"""
        if index == 1:  # View Catalog tab
            self.refresh_catalog_view()
        elif index == 2:  # Analytics tab
            self.refresh_analytics()
        elif index == 3:  # Maintenance tab
            # Populate current values when maintenance tab is opened
            keyword = self.keyword_combo.currentText()
            self.populate_current_values(keyword)


def main():
    app = QApplication(sys.argv)
    
    # Load theme setting
    settings = QSettings('XISFCatalog', 'CatalogGUI')
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
