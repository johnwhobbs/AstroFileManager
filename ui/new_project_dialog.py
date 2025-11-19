"""
New Project Dialog for AstroFileManager

Dialog for creating new imaging projects with template support.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QGroupBox, QHeaderView
)
from PyQt6.QtCore import Qt
from typing import Optional, Dict
from datetime import datetime

from core.project_templates import get_templates, create_filter_goals_dict
from core.project_manager import ProjectManager


class NewProjectDialog(QDialog):
    """Dialog for creating a new project."""

    def __init__(self, db_path: str, parent=None):
        """
        Initialize New Project dialog.

        Args:
            db_path: Path to SQLite database
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.project_manager = ProjectManager(db_path)
        self.templates = get_templates()
        self.current_filter_goals = {}

        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Project Details Section
        details_group = QGroupBox("Project Details")
        details_layout = QFormLayout()

        # Template selection
        self.template_combo = QComboBox()
        for template in self.templates:
            self.template_combo.addItem(template.name)
        self.template_combo.currentIndexChanged.connect(self.on_template_changed)
        details_layout.addRow("Template:", self.template_combo)

        # Template description
        self.template_desc = QLabel()
        self.template_desc.setWordWrap(True)
        self.template_desc.setStyleSheet("color: #666; font-style: italic;")
        details_layout.addRow("", self.template_desc)

        # Project name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., M31 Narrowband 2024")
        details_layout.addRow("Project Name*:", self.name_edit)

        # Object name
        self.object_edit = QLineEdit()
        self.object_edit.setPlaceholderText("e.g., M31")
        details_layout.addRow("Object Name*:", self.object_edit)

        # Year (optional)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setSpecialValueText("(Optional)")
        details_layout.addRow("Year:", self.year_spin)

        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(
            "Optional description of the project, equipment, goals, etc."
        )
        self.description_edit.setMaximumHeight(80)
        details_layout.addRow("Description:", self.description_edit)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Filter Goals Section
        goals_group = QGroupBox("Filter Goals")
        goals_layout = QVBoxLayout()

        # Filter goals table
        self.goals_table = QTableWidget()
        self.goals_table.setColumnCount(2)
        self.goals_table.setHorizontalHeaderLabels(["Filter", "Target Frames"])
        self.goals_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.goals_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.goals_table.setMaximumHeight(200)
        goals_layout.addWidget(self.goals_table)

        # Custom filter buttons (only shown for Custom template)
        custom_buttons_layout = QHBoxLayout()
        self.add_filter_btn = QPushButton("Add Filter")
        self.add_filter_btn.clicked.connect(self.add_custom_filter)
        self.remove_filter_btn = QPushButton("Remove Selected")
        self.remove_filter_btn.clicked.connect(self.remove_custom_filter)
        custom_buttons_layout.addWidget(self.add_filter_btn)
        custom_buttons_layout.addWidget(self.remove_filter_btn)
        custom_buttons_layout.addStretch()

        self.custom_buttons_widget = QGroupBox()
        self.custom_buttons_widget.setLayout(custom_buttons_layout)
        self.custom_buttons_widget.setVisible(False)
        goals_layout.addWidget(self.custom_buttons_widget)

        goals_group.setLayout(goals_layout)
        layout.addWidget(goals_group)

        # Dialog buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Create Project")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self.create_project)
        buttons_layout.addWidget(create_btn)

        layout.addLayout(buttons_layout)

        # Initialize with first template
        self.on_template_changed(0)

    def on_template_changed(self, index: int):
        """
        Handle template selection change.

        Args:
            index: Selected template index
        """
        template = self.templates[index]

        # Update description
        self.template_desc.setText(template.description)

        # Update filter goals
        self.current_filter_goals = create_filter_goals_dict(template)
        self.update_goals_table()

        # Show/hide custom buttons
        is_custom = template.name == "Custom"
        self.custom_buttons_widget.setVisible(is_custom)
        self.goals_table.setEditTriggers(
            QTableWidget.EditTrigger.AllEditTriggers if is_custom
            else QTableWidget.EditTrigger.NoEditTriggers
        )

    def update_goals_table(self):
        """Update the filter goals table with current goals."""
        self.goals_table.setRowCount(len(self.current_filter_goals))

        for row, (filter_name, target_count) in enumerate(self.current_filter_goals.items()):
            # Filter name
            filter_item = QTableWidgetItem(filter_name)
            self.goals_table.setItem(row, 0, filter_item)

            # Target count
            count_item = QTableWidgetItem(str(target_count))
            self.goals_table.setItem(row, 1, count_item)

    def add_custom_filter(self):
        """Add a new custom filter row."""
        row = self.goals_table.rowCount()
        self.goals_table.insertRow(row)

        # Default values
        filter_item = QTableWidgetItem("New Filter")
        count_item = QTableWidgetItem("90")

        self.goals_table.setItem(row, 0, filter_item)
        self.goals_table.setItem(row, 1, count_item)

        # Start editing the filter name
        self.goals_table.editItem(filter_item)

    def remove_custom_filter(self):
        """Remove selected filter row."""
        current_row = self.goals_table.currentRow()
        if current_row >= 0:
            self.goals_table.removeRow(current_row)

    def get_filter_goals_from_table(self) -> Dict[str, int]:
        """
        Extract filter goals from table.

        Returns:
            Dictionary mapping filter names to target counts
        """
        goals = {}
        for row in range(self.goals_table.rowCount()):
            filter_item = self.goals_table.item(row, 0)
            count_item = self.goals_table.item(row, 1)

            if filter_item and count_item:
                filter_name = filter_item.text().strip()
                try:
                    target_count = int(count_item.text())
                    if filter_name and target_count > 0:
                        goals[filter_name] = target_count
                except ValueError:
                    pass

        return goals

    def validate_inputs(self) -> tuple[bool, str]:
        """
        Validate user inputs.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check project name
        name = self.name_edit.text().strip()
        if not name:
            return False, "Project name is required"

        # Check object name
        object_name = self.object_edit.text().strip()
        if not object_name:
            return False, "Object name is required"

        # Check filter goals
        goals = self.get_filter_goals_from_table()
        if not goals:
            return False, "At least one filter goal is required"

        return True, ""

    def create_project(self):
        """Create the project."""
        # Validate inputs
        is_valid, error_msg = self.validate_inputs()
        if not is_valid:
            QMessageBox.warning(self, "Validation Error", error_msg)
            return

        try:
            # Get values
            name = self.name_edit.text().strip()
            object_name = self.object_edit.text().strip()
            description = self.description_edit.toPlainText().strip() or None
            year = self.year_spin.value() if self.year_spin.value() > 0 else None
            start_date = datetime.now().strftime("%Y-%m-%d")

            # Get filter goals
            filter_goals = self.get_filter_goals_from_table()

            # Create project
            project_id = self.project_manager.create_project(
                name=name,
                object_name=object_name,
                filter_goals=filter_goals,
                description=description,
                year=year,
                start_date=start_date
            )

            QMessageBox.information(
                self,
                "Success",
                f"Project '{name}' created successfully!\n\nProject ID: {project_id}"
            )

            self.accept()

        except Exception as e:
            error_msg = str(e)
            if "UNIQUE constraint failed" in error_msg:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"A project with the name '{name}' already exists.\n"
                    "Please choose a different name."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create project:\n{error_msg}"
                )
