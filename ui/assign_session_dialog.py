"""
Assign Session to Project Dialog for AstroFileManager

Dialog for assigning imaging sessions to projects.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTextEdit, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt
from typing import Optional

from core.project_manager import ProjectManager


class AssignSessionDialog(QDialog):
    """Dialog for assigning a session to a project."""

    def __init__(
        self,
        db_path: str,
        date_loc: str,
        object_name: str,
        filter_name: Optional[str],
        frame_count: int,
        parent=None
    ):
        """
        Initialize Assign Session dialog.

        Args:
            db_path: Path to SQLite database
            date_loc: Session date
            object_name: Object name
            filter_name: Filter name (or None)
            frame_count: Number of frames in session
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.date_loc = date_loc
        self.object_name = object_name
        self.filter_name = filter_name
        self.frame_count = frame_count
        self.project_manager = ProjectManager(db_path)

        self.setWindowTitle("Assign Session to Project")
        self.setMinimumWidth(500)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Session info
        info_group = QGroupBox("Session Information")
        info_layout = QVBoxLayout()

        info_layout.addWidget(QLabel(f"<b>Date:</b> {self.date_loc}"))
        info_layout.addWidget(QLabel(f"<b>Object:</b> {self.object_name}"))

        filter_text = self.filter_name if self.filter_name else "All filters"
        info_layout.addWidget(QLabel(f"<b>Filter:</b> {filter_text}"))

        info_layout.addWidget(QLabel(f"<b>Frame Count:</b> {self.frame_count}"))

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Project selection
        project_group = QGroupBox("Select Project")
        project_layout = QVBoxLayout()

        project_layout.addWidget(QLabel("Assign to Project:"))

        self.project_combo = QComboBox()
        self.load_projects()
        project_layout.addWidget(self.project_combo)

        # Project description display
        self.project_desc_label = QLabel()
        self.project_desc_label.setWordWrap(True)
        self.project_desc_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        project_layout.addWidget(self.project_desc_label)

        self.project_combo.currentIndexChanged.connect(self.on_project_changed)

        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        # Notes
        notes_label = QLabel("Notes (optional):")
        layout.addWidget(notes_label)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes about this session...")
        self.notes_edit.setMaximumHeight(80)
        layout.addWidget(self.notes_edit)

        # Dialog buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        assign_btn = QPushButton("Assign to Project")
        assign_btn.setDefault(True)
        assign_btn.clicked.connect(self.assign_session)
        buttons_layout.addWidget(assign_btn)

        layout.addLayout(buttons_layout)

        # Initialize project description
        if self.project_combo.count() > 0:
            self.on_project_changed(0)

    def load_projects(self):
        """Load active projects into combo box."""
        projects = self.project_manager.list_projects(status='active')

        if not projects:
            self.project_combo.addItem("(No active projects)", None)
            return

        for project in projects:
            display_text = f"{project.name} - {project.object_name}"
            self.project_combo.addItem(display_text, project.id)

    def on_project_changed(self, index: int):
        """
        Handle project selection change.

        Args:
            index: Selected project index
        """
        project_id = self.project_combo.itemData(index)

        if project_id is None:
            self.project_desc_label.setText("")
            return

        # Load project details
        project = self.project_manager.get_project(project_id)
        if project and project.description:
            self.project_desc_label.setText(project.description)
        else:
            self.project_desc_label.setText("")

    def assign_session(self):
        """Assign the session to the selected project."""
        project_id = self.project_combo.currentData()

        if project_id is None:
            QMessageBox.warning(
                self,
                "No Project",
                "Please create a project first before assigning sessions."
            )
            return

        try:
            # Generate session ID
            filter_suffix = f"_{self.filter_name}" if self.filter_name else ""
            session_id = f"{self.date_loc}_{self.object_name}{filter_suffix}"

            # Get notes
            notes = self.notes_edit.toPlainText().strip() or None

            # Assign session
            self.project_manager.assign_session_to_project(
                project_id=project_id,
                session_id=session_id,
                date_loc=self.date_loc,
                object_name=self.object_name,
                filter_name=self.filter_name,
                notes=notes
            )

            # Get project name for confirmation
            project = self.project_manager.get_project(project_id)
            project_name = project.name if project else "Project"

            QMessageBox.information(
                self,
                "Success",
                f"Session assigned to '{project_name}'!\n\n"
                f"{self.frame_count} frames linked to project."
            )

            self.accept()

        except Exception as e:
            error_msg = str(e)
            if "UNIQUE constraint failed" in error_msg:
                QMessageBox.critical(
                    self,
                    "Already Assigned",
                    "This session is already assigned to this project."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to assign session:\n{error_msg}"
                )
