#!/usr/bin/env python3
"""
AstroFileManager - XISF File Management for Astrophotography
A PyQt6-based application for cataloging, organizing, and managing XISF astrophotography files.
"""

import sys
from typing import Any
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget
from PyQt6.QtCore import Qt

# Import constants
from constants import (
    TEMP_TOLERANCE_DARKS, TEMP_TOLERANCE_FLATS, TEMP_TOLERANCE_BIAS,
    EXPOSURE_TOLERANCE, MIN_FRAMES_RECOMMENDED, MIN_FRAMES_ACCEPTABLE,
    IMPORT_BATCH_SIZE, DATE_OFFSET_HOURS
)

# Import core business logic modules
from core.database import DatabaseManager
from core.calibration import CalibrationMatcher
from core.config_manager import ConfigManager

# Import UI modules
from ui.import_tab import ImportTab
from ui.settings_tab import SettingsTab
from ui.maintenance_tab import MaintenanceTab
from ui.sessions_tab import SessionsTab
from ui.analytics_tab import AnalyticsTab
from ui.view_catalog_tab import ViewCatalogTab
from ui.projects_tab import ProjectsTab


class XISFCatalogGUI(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.db_path = 'xisf_catalog.db'
        self.settings = ConfigManager('AstroFileManager', 'AstroFileManager')

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

    def init_ui(self) -> None:
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
        self.sessions_tab = SessionsTab(self.db_path, self.db, self.calibration, self.settings)
        self.view_tab = ViewCatalogTab(
            db_path=self.db_path,
            settings=self.settings,
            status_callback=self.statusBar().showMessage,
            reimport_callback=self.import_tab.start_import
        )
        self.analytics_tab = AnalyticsTab(self.db_path, self.settings)
        self.projects_tab = ProjectsTab(self.db_path, self.settings, self.calibration)

        # Set cross-tab dependencies after all tabs are created
        self.import_tab.clear_db_btn = self.maintenance_tab.clear_db_btn
        self.clear_db_btn = self.maintenance_tab.clear_db_btn  # For backward compatibility

        tabs.addTab(self.view_tab, "View Catalog")
        tabs.addTab(self.projects_tab, "Projects")
        tabs.addTab(self.sessions_tab, "Sessions")
        tabs.addTab(self.analytics_tab, "Analytics")
        tabs.addTab(self.import_tab, "Import Files")
        tabs.addTab(self.maintenance_tab, "Maintenance")
        tabs.addTab(self.settings_tab, "Settings")
        
        # Connect tab change to refresh
        tabs.currentChanged.connect(self.on_tab_changed)

    def connect_signals(self) -> None:
        """Connect signals after all widgets are created"""
        # Connect column resize signals to save settings
        self.view_tab.catalog_tree.header().sectionResized.connect(self.save_settings)
        self.sessions_tab.sessions_tree.header().sectionResized.connect(self.save_settings)
    
    def save_settings(self) -> None:
        """Save window size and column widths"""
        # Save window geometry
        self.settings.setValue('geometry', self.saveGeometry())

        # Save catalog tree column widths
        for i in range(self.view_tab.catalog_tree.columnCount()):
            self.settings.setValue(f'catalog_tree_col_{i}', self.view_tab.catalog_tree.columnWidth(i))

        # Save sessions tree column widths
        for i in range(self.sessions_tab.sessions_tree.columnCount()):
            self.settings.setValue(f'sessions_tree_col_{i}', self.sessions_tab.sessions_tree.columnWidth(i))

        # Save sessions tab splitter state
        self.sessions_tab.save_splitter_state()

        # Save projects tab splitter state
        self.projects_tab.save_splitter_state()
    
    def restore_settings(self) -> None:
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

        # Restore sessions tab splitter state
        self.sessions_tab.restore_splitter_state()

        # Restore projects tab splitter state
        self.projects_tab.restore_splitter_state()

        # Connect signals after restoring settings to avoid triggering saves during restore
        self.connect_signals()
    
    def closeEvent(self, event: Any) -> None:
        """Save settings when closing"""
        self.save_settings()
        event.accept()
    
    def on_tab_changed(self, index: int) -> None:
        """Handle tab change"""
        if index == 0:  # View Catalog tab
            self.view_tab.refresh_catalog_view()
        elif index == 1:  # Projects tab
            self.projects_tab.refresh_projects()
        elif index == 2:  # Sessions tab
            self.sessions_tab.refresh_sessions()
        elif index == 3:  # Analytics tab
            self.analytics_tab.refresh_analytics()
        elif index == 5:  # Maintenance tab
            # Populate current values when maintenance tab is opened
            keyword = self.maintenance_tab.keyword_combo.currentText()
            self.maintenance_tab.populate_current_values(keyword)



def main() -> None:
    app = QApplication(sys.argv)

    # Load theme setting
    settings = ConfigManager('AstroFileManager', 'AstroFileManager')
    theme = settings.value('theme', 'standard')
    
    # Apply theme
    if theme == 'dark':
        apply_dark_theme(app)
    else:
        apply_standard_theme(app)
    
    window = XISFCatalogGUI()
    window.show()
    sys.exit(app.exec())


def apply_dark_theme(app: QApplication) -> None:
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


def apply_standard_theme(app: QApplication) -> None:
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
