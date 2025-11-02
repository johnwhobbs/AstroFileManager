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
    QTreeWidgetItem
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
                    'EXPOSURE', 'CCD-TEMP', 'XBINNING', 'YBINNING', 'DATE-LOC']
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
            
            return results
        except Exception as e:
            return None
    
    def run(self):
        """Process files and import to database"""
        conn = sqlite3.connect(self.db_path)
        
        for i, filepath in enumerate(self.files):
            basename = os.path.basename(filepath)
            self.progress.emit(i + 1, len(self.files), f"Processing: {basename}")
            
            try:
                # Calculate hash
                file_hash = self.calculate_file_hash(filepath)
                
                # Read FITS keywords
                keywords = self.read_fits_keywords(filepath)
                
                if keywords:
                    cursor = conn.cursor()
                    
                    # Check if exists
                    cursor.execute('SELECT id FROM xisf_files WHERE file_hash = ?', (file_hash,))
                    existing = cursor.fetchone()
                    
                    filename = os.path.basename(filepath)
                    
                    # Process DATE-LOC to subtract 12 hours and get date only
                    date_loc = self.process_date_loc(keywords.get('DATE-LOC'))
                    
                    if existing:
                        cursor.execute('''
                            UPDATE xisf_files
                            SET filepath = ?, filename = ?, telescop = ?, instrume = ?, 
                                object = ?, filter = ?, imagetyp = ?, exposure = ?,
                                ccd_temp = ?, xbinning = ?, ybinning = ?, date_loc = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE file_hash = ?
                        ''', (
                            filepath, filename,
                            keywords.get('TELESCOP'), keywords.get('INSTRUME'),
                            keywords.get('OBJECT'), keywords.get('FILTER'),
                            keywords.get('IMAGETYP'), keywords.get('EXPOSURE'),
                            keywords.get('CCD-TEMP'), keywords.get('XBINNING'),
                            keywords.get('YBINNING'), date_loc,
                            file_hash
                        ))
                    else:
                        cursor.execute('''
                            INSERT INTO xisf_files 
                            (file_hash, filepath, filename, telescop, instrume, object, 
                             filter, imagetyp, exposure, ccd_temp, xbinning, ybinning, date_loc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            file_hash, filepath, filename,
                            keywords.get('TELESCOP'), keywords.get('INSTRUME'),
                            keywords.get('OBJECT'), keywords.get('FILTER'),
                            keywords.get('IMAGETYP'), keywords.get('EXPOSURE'),
                            keywords.get('CCD-TEMP'), keywords.get('XBINNING'),
                            keywords.get('YBINNING'), date_loc
                        ))
                    
                    conn.commit()
                    self.processed += 1
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
        self.stats_tab = self.create_stats_tab()
        
        tabs.addTab(self.import_tab, "Import Files")
        tabs.addTab(self.view_tab, "View Catalog")
        tabs.addTab(self.stats_tab, "Statistics")
        
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
        
        self.clear_db_btn = QPushButton('Clear Database')
        self.clear_db_btn.clicked.connect(self.clear_database)
        self.clear_db_btn.setStyleSheet("QPushButton { background-color: #8b0000; color: white; } QPushButton:hover { background-color: #a00000; }")
        button_layout.addWidget(self.clear_db_btn)
        
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
    
    def create_stats_tab(self):
        """Create the statistics tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Refresh button
        refresh_btn = QPushButton('Refresh Statistics')
        refresh_btn.clicked.connect(self.refresh_statistics)
        layout.addWidget(refresh_btn)
        
        # Horizontal layout for two tables side by side
        tables_layout = QHBoxLayout()
        
        # Left side - Most Recent Objects
        left_layout = QVBoxLayout()
        recent_label = QLabel('10 Most Recent Objects')
        recent_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(recent_label)
        
        self.recent_objects_table = QTableWidget()
        self.recent_objects_table.setColumnCount(4)
        self.recent_objects_table.setHorizontalHeaderLabels(['Object', 'Most Recent Date', 'Telescope', 'Instrument'])
        self.recent_objects_table.horizontalHeader().setStretchLastSection(True)
        self.recent_objects_table.horizontalHeader().setSectionsMovable(False)
        self.recent_objects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_objects_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        left_layout.addWidget(self.recent_objects_table)
        
        tables_layout.addLayout(left_layout)
        
        # Right side - Top Exposure Objects
        right_layout = QVBoxLayout()
        exposure_label = QLabel('Top 10 Objects by Total Exposure')
        exposure_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(exposure_label)
        
        self.top_exposure_table = QTableWidget()
        self.top_exposure_table.setColumnCount(4)
        self.top_exposure_table.setHorizontalHeaderLabels(['Object', 'Total Exposure (hrs)', 'Telescope', 'Instrument'])
        self.top_exposure_table.horizontalHeader().setStretchLastSection(True)
        self.top_exposure_table.horizontalHeader().setSectionsMovable(False)
        self.top_exposure_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.top_exposure_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        right_layout.addWidget(self.top_exposure_table)
        
        tables_layout.addLayout(right_layout)
        
        layout.addLayout(tables_layout)
        
        return widget
    
    def connect_signals(self):
        """Connect signals after all widgets are created"""
        # Connect column resize signals to save settings
        self.catalog_tree.header().sectionResized.connect(self.save_settings)
        self.recent_objects_table.horizontalHeader().sectionResized.connect(self.save_settings)
        self.top_exposure_table.horizontalHeader().sectionResized.connect(self.save_settings)
    
    def refresh_statistics(self):
        """Refresh the statistics tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get 10 most recent objects with their telescope and instrument
            cursor.execute('''
                SELECT 
                    f1.object,
                    f1.date_loc,
                    f1.telescop,
                    f1.instrume
                FROM xisf_files f1
                INNER JOIN (
                    SELECT object, MAX(date_loc) as max_date
                    FROM xisf_files
                    WHERE object IS NOT NULL AND date_loc IS NOT NULL
                    GROUP BY object
                ) f2 ON f1.object = f2.object AND f1.date_loc = f2.max_date
                WHERE f1.object IS NOT NULL AND f1.date_loc IS NOT NULL
                GROUP BY f1.object
                ORDER BY f1.date_loc DESC
                LIMIT 10
            ''')
            
            recent_objects = cursor.fetchall()
            
            # Update recent objects table
            self.recent_objects_table.setRowCount(len(recent_objects))
            for i, (obj, date, telescop, instrume) in enumerate(recent_objects):
                self.recent_objects_table.setItem(i, 0, QTableWidgetItem(obj or 'Unknown'))
                self.recent_objects_table.setItem(i, 1, QTableWidgetItem(date or 'N/A'))
                self.recent_objects_table.setItem(i, 2, QTableWidgetItem(telescop or 'N/A'))
                self.recent_objects_table.setItem(i, 3, QTableWidgetItem(instrume or 'N/A'))
            
            self.recent_objects_table.resizeColumnsToContents()
            
            # Get top 10 objects by total exposure
            cursor.execute('''
                SELECT 
                    f1.object,
                    SUM(f1.exposure) as total_exposure,
                    (SELECT telescop FROM xisf_files WHERE object = f1.object LIMIT 1) as telescop,
                    (SELECT instrume FROM xisf_files WHERE object = f1.object LIMIT 1) as instrume
                FROM xisf_files f1
                WHERE f1.object IS NOT NULL AND f1.exposure IS NOT NULL
                GROUP BY f1.object
                ORDER BY total_exposure DESC
                LIMIT 10
            ''')
            
            top_exposure_objects = cursor.fetchall()
            
            # Update top exposure table
            self.top_exposure_table.setRowCount(len(top_exposure_objects))
            for i, (obj, total_exp, telescop, instrume) in enumerate(top_exposure_objects):
                self.top_exposure_table.setItem(i, 0, QTableWidgetItem(obj or 'Unknown'))
                self.top_exposure_table.setItem(i, 1, QTableWidgetItem(f'{total_exp/3600:.2f}' if total_exp else '0.00'))
                self.top_exposure_table.setItem(i, 2, QTableWidgetItem(telescop or 'N/A'))
                self.top_exposure_table.setItem(i, 3, QTableWidgetItem(instrume or 'N/A'))
            
            self.top_exposure_table.resizeColumnsToContents()
            
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh statistics: {e}')
    
    def save_settings(self):
        """Save window size and column widths"""
        # Save window geometry
        self.settings.setValue('geometry', self.saveGeometry())
        
        # Save catalog tree column widths
        for i in range(self.catalog_tree.columnCount()):
            self.settings.setValue(f'catalog_tree_col_{i}', self.catalog_tree.columnWidth(i))
        
        # Save recent objects table column widths (all except last which is stretched)
        for i in range(self.recent_objects_table.columnCount() - 1):
            width = self.recent_objects_table.columnWidth(i)
            self.settings.setValue(f'recent_table_col_{i}', width)
        
        # Save top exposure table column widths (all except last which is stretched)
        for i in range(self.top_exposure_table.columnCount() - 1):
            width = self.top_exposure_table.columnWidth(i)
            self.settings.setValue(f'exposure_table_col_{i}', width)
    
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
        
        # Restore recent objects table column widths (all except last which is stretched)
        for i in range(self.recent_objects_table.columnCount() - 1):
            width = self.settings.value(f'recent_table_col_{i}')
            if width is not None:
                self.recent_objects_table.setColumnWidth(i, int(width))
        
        # Restore top exposure table column widths (all except last which is stretched)
        for i in range(self.top_exposure_table.columnCount() - 1):
            width = self.settings.value(f'exposure_table_col_{i}')
            if width is not None:
                self.top_exposure_table.setColumnWidth(i, int(width))
        
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
            
            # Get all objects
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
                obj_item = QTreeWidgetItem(self.catalog_tree)
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
            
            conn.close()
            
            # Expand all top-level items by default
            for i in range(self.catalog_tree.topLevelItemCount()):
                item = self.catalog_tree.topLevelItem(i)
                self.catalog_tree.expandItem(item)
            
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh view: {e}')
    
    def on_tab_changed(self, index):
        """Handle tab change"""
        if index == 1:  # View Catalog tab
            self.refresh_catalog_view()
        elif index == 2:  # Statistics tab
            self.refresh_statistics()


def main():
    app = QApplication(sys.argv)
    
    # Set dark theme
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
    """)
    
    window = XISFCatalogGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()