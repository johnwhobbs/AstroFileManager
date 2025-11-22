"""
Enhanced styling for AstroFileManager application.

Provides modern QSS stylesheets for both dark and standard themes.
"""


def get_dark_theme_stylesheet() -> str:
    """Return enhanced dark theme stylesheet."""
    return """
        /* Main Window and Base Widgets */
        QMainWindow, QDialog {
            background-color: #1e1e1e;
        }

        /* Buttons - Modern flat design with hover effects */
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 500;
            min-height: 24px;
        }

        QPushButton:hover {
            background-color: #106ebe;
        }

        QPushButton:pressed {
            background-color: #005a9e;
        }

        QPushButton:disabled {
            background-color: #3d3d3d;
            color: #888888;
        }

        /* Secondary buttons (Refresh, Cancel, etc.) */
        QPushButton[class="secondary"] {
            background-color: #404040;
            border: 1px solid #555555;
        }

        QPushButton[class="secondary"]:hover {
            background-color: #505050;
        }

        /* Danger buttons (Delete, Clear, etc.) */
        QPushButton[class="danger"] {
            background-color: #c42b1c;
        }

        QPushButton[class="danger"]:hover {
            background-color: #a52314;
        }

        /* Success buttons (Approve, etc.) */
        QPushButton[class="success"] {
            background-color: #107c10;
        }

        QPushButton[class="success"]:hover {
            background-color: #0d5f0d;
        }

        /* Tables and Trees */
        QTableWidget, QTreeWidget {
            background-color: #252525;
            alternate-background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            gridline-color: #3d3d3d;
            selection-background-color: #0078d4;
            selection-color: white;
        }

        QTableWidget::item, QTreeWidget::item {
            padding: 4px;
        }

        QTableWidget::item:hover, QTreeWidget::item:hover {
            background-color: #333333;
        }

        QTableWidget::item:selected, QTreeWidget::item:selected {
            background-color: #0078d4;
            color: white;
        }

        /* Headers */
        QHeaderView::section {
            background-color: #2d2d2d;
            color: #ffffff;
            padding: 6px 4px;
            border: none;
            border-right: 1px solid #3d3d3d;
            border-bottom: 2px solid #0078d4;
            font-weight: 600;
            font-size: 11pt;
        }

        QHeaderView::section:hover {
            background-color: #353535;
        }

        /* Scrollbars */
        QScrollBar:vertical {
            border: none;
            background-color: #2d2d2d;
            width: 12px;
            margin: 0;
        }

        QScrollBar::handle:vertical {
            background-color: #555555;
            border-radius: 6px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #666666;
        }

        QScrollBar:horizontal {
            border: none;
            background-color: #2d2d2d;
            height: 12px;
            margin: 0;
        }

        QScrollBar::handle:horizontal {
            background-color: #555555;
            border-radius: 6px;
            min-width: 20px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #666666;
        }

        QScrollBar::add-line, QScrollBar::sub-line {
            border: none;
            background: none;
        }

        /* Progress Bars */
        QProgressBar {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            text-align: center;
            background-color: #2d2d2d;
            color: white;
            font-weight: 500;
        }

        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                             stop:0 #0078d4, stop:1 #00bcf2);
            border-radius: 3px;
        }

        /* Group Boxes - Card style */
        QGroupBox {
            background-color: #252525;
            border: 1px solid #3d3d3d;
            border-radius: 6px;
            margin-top: 12px;
            padding: 15px;
            font-weight: 600;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            color: #ffffff;
        }

        /* Input Fields */
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 6px;
            color: white;
            selection-background-color: #0078d4;
        }

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid #0078d4;
        }

        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
            background-color: #1e1e1e;
            color: #888888;
        }

        /* Combo Boxes */
        QComboBox {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 6px;
            color: white;
            min-width: 100px;
        }

        QComboBox:hover {
            border: 1px solid #555555;
        }

        QComboBox::drop-down {
            border: none;
            width: 20px;
        }

        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #ffffff;
            margin-right: 6px;
        }

        QComboBox QAbstractItemView {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            selection-background-color: #0078d4;
            selection-color: white;
            outline: none;
        }

        /* Tab Widget */
        QTabWidget::pane {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            background-color: #1e1e1e;
        }

        QTabBar::tab {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
            color: #cccccc;
        }

        QTabBar::tab:selected {
            background-color: #1e1e1e;
            color: #ffffff;
            border-bottom: 2px solid #0078d4;
        }

        QTabBar::tab:hover:!selected {
            background-color: #353535;
        }

        /* Tooltips */
        QToolTip {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #0078d4;
            border-radius: 4px;
            padding: 6px;
            font-size: 10pt;
        }

        /* Labels */
        QLabel {
            color: #ffffff;
        }

        /* Splitters */
        QSplitter::handle {
            background-color: #3d3d3d;
        }

        QSplitter::handle:hover {
            background-color: #0078d4;
        }

        QSplitter::handle:horizontal {
            width: 2px;
        }

        QSplitter::handle:vertical {
            height: 2px;
        }

        /* Status Bar */
        QStatusBar {
            background-color: #2d2d2d;
            color: #ffffff;
            border-top: 1px solid #3d3d3d;
        }

        /* Checkboxes */
        QCheckBox {
            color: white;
            spacing: 8px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #3d3d3d;
            border-radius: 3px;
            background-color: #2d2d2d;
        }

        QCheckBox::indicator:hover {
            border: 1px solid #0078d4;
        }

        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border: 1px solid #0078d4;
        }

        /* Radio Buttons */
        QRadioButton {
            color: white;
            spacing: 8px;
        }

        QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #3d3d3d;
            border-radius: 9px;
            background-color: #2d2d2d;
        }

        QRadioButton::indicator:hover {
            border: 1px solid #0078d4;
        }

        QRadioButton::indicator:checked {
            background-color: #0078d4;
            border: 1px solid #0078d4;
        }
    """


def get_standard_theme_stylesheet() -> str:
    """Return enhanced standard (light) theme stylesheet."""
    return """
        /* Main Window and Base Widgets */
        QMainWindow, QDialog {
            background-color: #f5f5f5;
        }

        /* Buttons - Modern flat design with hover effects */
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 500;
            min-height: 24px;
        }

        QPushButton:hover {
            background-color: #106ebe;
        }

        QPushButton:pressed {
            background-color: #005a9e;
        }

        QPushButton:disabled {
            background-color: #e0e0e0;
            color: #a0a0a0;
        }

        /* Secondary buttons */
        QPushButton[class="secondary"] {
            background-color: #f0f0f0;
            color: #333333;
            border: 1px solid #cccccc;
        }

        QPushButton[class="secondary"]:hover {
            background-color: #e5e5e5;
        }

        /* Danger buttons */
        QPushButton[class="danger"] {
            background-color: #d13438;
        }

        QPushButton[class="danger"]:hover {
            background-color: #a52a2e;
        }

        /* Success buttons */
        QPushButton[class="success"] {
            background-color: #107c10;
        }

        QPushButton[class="success"]:hover {
            background-color: #0d5f0d;
        }

        /* Tables and Trees */
        QTableWidget, QTreeWidget {
            background-color: white;
            alternate-background-color: #f9f9f9;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            gridline-color: #e0e0e0;
            selection-background-color: #0078d4;
            selection-color: white;
        }

        QTableWidget::item, QTreeWidget::item {
            padding: 4px;
        }

        QTableWidget::item:hover, QTreeWidget::item:hover {
            background-color: #f0f0f0;
        }

        QTableWidget::item:selected, QTreeWidget::item:selected {
            background-color: #0078d4;
            color: white;
        }

        /* Headers */
        QHeaderView::section {
            background-color: #f0f0f0;
            color: #333333;
            padding: 6px 4px;
            border: none;
            border-right: 1px solid #d0d0d0;
            border-bottom: 2px solid #0078d4;
            font-weight: 600;
            font-size: 11pt;
        }

        QHeaderView::section:hover {
            background-color: #e5e5e5;
        }

        /* Scrollbars */
        QScrollBar:vertical {
            border: none;
            background-color: #f0f0f0;
            width: 12px;
            margin: 0;
        }

        QScrollBar::handle:vertical {
            background-color: #c0c0c0;
            border-radius: 6px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #a0a0a0;
        }

        QScrollBar:horizontal {
            border: none;
            background-color: #f0f0f0;
            height: 12px;
            margin: 0;
        }

        QScrollBar::handle:horizontal {
            background-color: #c0c0c0;
            border-radius: 6px;
            min-width: 20px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #a0a0a0;
        }

        QScrollBar::add-line, QScrollBar::sub-line {
            border: none;
            background: none;
        }

        /* Progress Bars */
        QProgressBar {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            text-align: center;
            background-color: #f0f0f0;
            color: #333333;
            font-weight: 500;
        }

        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                             stop:0 #0078d4, stop:1 #00bcf2);
            border-radius: 3px;
        }

        /* Group Boxes - Card style */
        QGroupBox {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            margin-top: 12px;
            padding: 15px;
            font-weight: 600;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            color: #333333;
        }

        /* Input Fields */
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 6px;
            color: #333333;
            selection-background-color: #0078d4;
        }

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid #0078d4;
        }

        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
            background-color: #f5f5f5;
            color: #a0a0a0;
        }

        /* Combo Boxes */
        QComboBox {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 6px;
            color: #333333;
            min-width: 100px;
        }

        QComboBox:hover {
            border: 1px solid #a0a0a0;
        }

        QComboBox::drop-down {
            border: none;
            width: 20px;
        }

        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #333333;
            margin-right: 6px;
        }

        QComboBox QAbstractItemView {
            background-color: white;
            border: 1px solid #d0d0d0;
            selection-background-color: #0078d4;
            selection-color: white;
            outline: none;
        }

        /* Tab Widget */
        QTabWidget::pane {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            background-color: #f5f5f5;
        }

        QTabBar::tab {
            background-color: #e5e5e5;
            border: 1px solid #d0d0d0;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
            color: #666666;
        }

        QTabBar::tab:selected {
            background-color: #f5f5f5;
            color: #333333;
            border-bottom: 2px solid #0078d4;
        }

        QTabBar::tab:hover:!selected {
            background-color: #d5d5d5;
        }

        /* Tooltips */
        QToolTip {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #0078d4;
            border-radius: 4px;
            padding: 6px;
            font-size: 10pt;
        }

        /* Labels */
        QLabel {
            color: #333333;
        }

        /* Splitters */
        QSplitter::handle {
            background-color: #d0d0d0;
        }

        QSplitter::handle:hover {
            background-color: #0078d4;
        }

        QSplitter::handle:horizontal {
            width: 2px;
        }

        QSplitter::handle:vertical {
            height: 2px;
        }

        /* Status Bar */
        QStatusBar {
            background-color: #f0f0f0;
            color: #333333;
            border-top: 1px solid #d0d0d0;
        }

        /* Checkboxes */
        QCheckBox {
            color: #333333;
            spacing: 8px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            background-color: white;
        }

        QCheckBox::indicator:hover {
            border: 1px solid #0078d4;
        }

        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border: 1px solid #0078d4;
        }

        /* Radio Buttons */
        QRadioButton {
            color: #333333;
            spacing: 8px;
        }

        QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #d0d0d0;
            border-radius: 9px;
            background-color: white;
        }

        QRadioButton::indicator:hover {
            border: 1px solid #0078d4;
        }

        QRadioButton::indicator:checked {
            background-color: #0078d4;
            border: 1px solid #0078d4;
        }
    """
