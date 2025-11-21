"""
Edit Project Dialog for AstroFileManager

Dialog for editing existing imaging projects.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QGroupBox, QHeaderView
)
from PyQt6.QtCore import Qt
from typing import Optional, Dict

from core.project_manager import ProjectManager, Project


class EditProjectDialog(QDialog):
    """Dialog for editing an existing project."""

    def __init__(self, db_path: str, project: Project, parent=None):
        """
        Initialize Edit Project dialog.

        Args:
            db_path: Path to SQLite database
            project: Project object to edit
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.project = project
        self.project_manager = ProjectManager(db_path)
        self.current_filter_goals = {}

        self.setWindowTitle(f"Edit Project: {project.name}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self.init_ui()
        self.load_project_data()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Project Details Section
        details_group = QGroupBox("Project Details")
        details_layout = QFormLayout()

        # Project Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., M31 Narrowband 2024")
        details_layout.addRow("Project Name:", self.name_input)

        # Object Name
        self.object_input = QLineEdit()
        self.object_input.setPlaceholderText("e.g., M31")
        details_layout.addRow("Object Name:", self.object_input)

        # Year (optional)
        self.year_input = QSpinBox()
        self.year_input.setMinimum(2000)
        self.year_input.setMaximum(2100)
        self.year_input.setValue(2024)
        self.year_input.setSpecialValueText("Not set")
        details_layout.addRow("Year (optional):", self.year_input)

        # Description (optional)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional notes about equipment, goals, etc.")
        self.description_input.setMaximumHeight(80)
        details_layout.addRow("Description:", self.description_input)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Filter Goals Section
        goals_group = QGroupBox("Filter Goals")
        goals_layout = QVBoxLayout()

        # Add/Remove filter buttons
        filter_buttons = QHBoxLayout()

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter name (e.g., Ha, OIII, L)")
        filter_buttons.addWidget(QLabel("Filter:"))
        filter_buttons.addWidget(self.filter_input)

        self.target_input = QSpinBox()
        self.target_input.setMinimum(1)
        self.target_input.setMaximum(10000)
        self.target_input.setValue(100)
        filter_buttons.addWidget(QLabel("Target:"))
        filter_buttons.addWidget(self.target_input)

        self.add_filter_btn = QPushButton("Add/Update Filter")
        self.add_filter_btn.clicked.connect(self.add_filter_goal)
        filter_buttons.addWidget(self.add_filter_btn)

        self.remove_filter_btn = QPushButton("Remove Filter")
        self.remove_filter_btn.clicked.connect(self.remove_filter_goal)
        filter_buttons.addWidget(self.remove_filter_btn)

        goals_layout.addLayout(filter_buttons)

        # Filter goals table
        self.goals_table = QTableWidget()
        self.goals_table.setColumnCount(2)
        self.goals_table.setHorizontalHeaderLabels(["Filter", "Target Count"])
        self.goals_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.goals_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.goals_table.itemSelectionChanged.connect(self.on_filter_selected)
        goals_layout.addWidget(self.goals_table)

        goals_group.setLayout(goals_layout)
        layout.addWidget(goals_group)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_project)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def load_project_data(self):
        """Load existing project data into the form."""
        # Load project details
        self.name_input.setText(self.project.name)
        self.object_input.setText(self.project.object_name)

        if self.project.year:
            self.year_input.setValue(self.project.year)
        else:
            self.year_input.setValue(self.year_input.minimum())

        if self.project.description:
            self.description_input.setPlainText(self.project.description)

        # Load filter goals
        goals = self.project_manager.get_filter_goals(self.project.id)
        for goal in goals:
            self.current_filter_goals[goal.filter] = goal.target_count

        self.update_goals_table()

    def update_goals_table(self):
        """Update the filter goals table display."""
        self.goals_table.setRowCount(len(self.current_filter_goals))

        for row, (filter_name, target) in enumerate(sorted(self.current_filter_goals.items())):
            filter_item = QTableWidgetItem(filter_name)
            target_item = QTableWidgetItem(str(target))

            self.goals_table.setItem(row, 0, filter_item)
            self.goals_table.setItem(row, 1, target_item)

    def on_filter_selected(self):
        """Handle filter selection in table."""
        selected_items = self.goals_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            filter_name = self.goals_table.item(row, 0).text()
            target = int(self.goals_table.item(row, 1).text())

            self.filter_input.setText(filter_name)
            self.target_input.setValue(target)

    def add_filter_goal(self):
        """Add or update a filter goal."""
        filter_name = self.filter_input.text().strip()
        if not filter_name:
            QMessageBox.warning(self, "Input Required", "Please enter a filter name.")
            return

        target_count = self.target_input.value()
        self.current_filter_goals[filter_name] = target_count

        self.update_goals_table()
        self.filter_input.clear()
        self.target_input.setValue(100)

    def remove_filter_goal(self):
        """Remove selected filter goal."""
        selected_items = self.goals_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a filter to remove.")
            return

        row = selected_items[0].row()
        filter_name = self.goals_table.item(row, 0).text()

        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove filter '{filter_name}' from project goals?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.current_filter_goals[filter_name]
            self.update_goals_table()

    def save_project(self):
        """Validate and save the edited project."""
        # Validate inputs
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Required", "Please enter a project name.")
            return

        object_name = self.object_input.text().strip()
        if not object_name:
            QMessageBox.warning(self, "Input Required", "Please enter an object name.")
            return

        if not self.current_filter_goals:
            QMessageBox.warning(
                self, "Input Required",
                "Please add at least one filter goal."
            )
            return

        # Get optional fields
        year = self.year_input.value() if self.year_input.value() > self.year_input.minimum() else None
        description = self.description_input.toPlainText().strip()

        # Check if name changed and conflicts with another project
        if name != self.project.name:
            existing = self.project_manager.get_project_by_name(name)
            if existing and existing.id != self.project.id:
                QMessageBox.warning(
                    self,
                    "Duplicate Name",
                    f"A project named '{name}' already exists. Please choose a different name."
                )
                return

        try:
            # Update project
            self.project_manager.update_project(
                project_id=self.project.id,
                name=name,
                object_name=object_name,
                year=year,
                description=description if description else None
            )

            # Update filter goals
            self.project_manager.update_filter_goals(
                project_id=self.project.id,
                filter_goals=self.current_filter_goals
            )

            QMessageBox.information(
                self,
                "Success",
                f"Project '{name}' has been updated successfully!"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to update project:\n{str(e)}"
            )
