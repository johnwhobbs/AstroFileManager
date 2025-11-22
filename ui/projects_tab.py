"""
Projects Tab for AstroFileManager

Displays and manages imaging projects with progress tracking.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QLabel, QGroupBox, QSplitter, QTextBrowser, QMessageBox,
    QComboBox, QFileDialog, QDialog
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QBrush
from typing import Optional

from core.project_manager import ProjectManager, Project, FilterGoalProgress
from ui.new_project_dialog import NewProjectDialog
from import_export.subframe_selector_importer import SubFrameSelectorImporter


class ProjectsTab(QWidget):
    """Tab for managing imaging projects."""

    def __init__(self, db_path: str, settings: QSettings):
        """
        Initialize Projects tab.

        Args:
            db_path: Path to SQLite database
            settings: QSettings object for storing user preferences
        """
        super().__init__()
        self.db_path = db_path
        self.settings = settings
        self.project_manager = ProjectManager(db_path)
        self.selected_project_id: Optional[int] = None
        self.current_goals_table: Optional[QTableWidget] = None  # Keep reference for signal connection

        self.init_ui()
        self.refresh_projects()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Top toolbar
        toolbar = QHBoxLayout()

        self.new_project_btn = QPushButton("➕ New Project")
        self.new_project_btn.clicked.connect(self.create_new_project)
        toolbar.addWidget(self.new_project_btn)

        self.edit_project_btn = QPushButton("✏️ Edit Project")
        self.edit_project_btn.clicked.connect(self.edit_project)
        self.edit_project_btn.setEnabled(False)  # Disabled until project is selected
        toolbar.addWidget(self.edit_project_btn)

        self.import_quality_btn = QPushButton("📥 Import Quality Data")
        self.import_quality_btn.clicked.connect(self.import_quality_data)
        toolbar.addWidget(self.import_quality_btn)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_projects)
        self.refresh_btn.setProperty("class", "secondary")
        toolbar.addWidget(self.refresh_btn)

        # Status filter
        toolbar.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active", "Completed", "Archived"])
        self.status_filter.currentTextChanged.connect(self.refresh_projects)
        toolbar.addWidget(self.status_filter)

        toolbar.addStretch()

        self.unassigned_label = QLabel()
        self.unassigned_label.setStyleSheet("color: #d9534f; font-weight: bold;")
        toolbar.addWidget(self.unassigned_label)

        layout.addLayout(toolbar)

        # Splitter for projects list and details
        self.projects_splitter = QSplitter(Qt.Orientation.Vertical)

        # Projects table
        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels([
            "Project Name", "Object", "Year", "Status", "Created"
        ])

        # Make columns resizable
        self.projects_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.projects_table.horizontalHeader().setStretchLastSection(True)

        # Set initial column widths or restore from settings
        default_widths = [200, 150, 80, 100, 100]  # Project Name, Object, Year, Status, Created
        for col in range(5):
            saved_width = self.settings.value(f'projects_table_col_{col}')
            if saved_width:
                self.projects_table.setColumnWidth(col, int(saved_width))
            else:
                self.projects_table.setColumnWidth(col, default_widths[col])

        # Connect column resize to save settings
        self.projects_table.horizontalHeader().sectionResized.connect(self.save_projects_table_column_widths)

        self.projects_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.projects_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.projects_table.itemSelectionChanged.connect(self.on_project_selected)
        self.projects_splitter.addWidget(self.projects_table)

        # Project details panel
        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)

        # Project info section
        self.info_label = QLabel("Select a project to view details")
        self.info_label.setWordWrap(True)
        details_layout.addWidget(self.info_label)

        # Create a splitter for goals and next steps sections
        self.details_content_splitter = QSplitter(Qt.Orientation.Vertical)

        # Filter goals progress
        self.goals_group = QGroupBox("Filter Goals Progress")
        self.goals_layout = QVBoxLayout()
        self.goals_group.setLayout(self.goals_layout)
        self.goals_group.setVisible(False)
        self.details_content_splitter.addWidget(self.goals_group)

        # Next steps / recommendations
        self.next_steps_group = QGroupBox("Next Steps")
        next_steps_layout = QVBoxLayout()
        self.next_steps_text = QTextBrowser()
        next_steps_layout.addWidget(self.next_steps_text)
        self.next_steps_group.setLayout(next_steps_layout)
        self.next_steps_group.setVisible(False)
        self.details_content_splitter.addWidget(self.next_steps_group)

        # Set initial proportions for goals and next steps (200:150 ratio)
        self.details_content_splitter.setSizes([200, 150])

        # Connect splitter movement to save settings
        self.details_content_splitter.splitterMoved.connect(self.save_details_content_splitter_state)

        details_layout.addWidget(self.details_content_splitter)

        # Action buttons
        action_buttons = QHBoxLayout()

        self.mark_complete_btn = QPushButton("✓ Mark Complete")
        self.mark_complete_btn.clicked.connect(self.mark_project_complete)
        self.mark_complete_btn.setVisible(False)
        self.mark_complete_btn.setProperty("class", "success")
        action_buttons.addWidget(self.mark_complete_btn)

        self.archive_btn = QPushButton("📦 Archive")
        self.archive_btn.clicked.connect(self.archive_project)
        self.archive_btn.setVisible(False)
        self.archive_btn.setProperty("class", "secondary")
        action_buttons.addWidget(self.archive_btn)

        self.delete_btn = QPushButton("🗑️ Delete Project")
        self.delete_btn.clicked.connect(self.delete_project)
        self.delete_btn.setVisible(False)
        self.delete_btn.setProperty("class", "danger")
        action_buttons.addWidget(self.delete_btn)

        action_buttons.addStretch()
        details_layout.addLayout(action_buttons)

        details_layout.addStretch()
        self.projects_splitter.addWidget(details_panel)

        # Set initial proportions: 70% for projects table, 30% for details
        # Use 400:200 ratio to give more space to the projects list
        self.projects_splitter.setSizes([400, 200])

        # Connect splitter movement to save settings
        self.projects_splitter.splitterMoved.connect(self.save_splitter_state)

        layout.addWidget(self.projects_splitter)

    def refresh_projects(self):
        """Refresh the projects list."""
        # Save the currently selected project ID to restore after refresh
        previously_selected_id = self.selected_project_id

        # Get status filter
        status_text = self.status_filter.currentText()
        status = None if status_text == "All" else status_text.lower()

        # Load projects
        projects = self.project_manager.list_projects(status=status)

        # Block signals to prevent on_project_selected from firing during update
        self.projects_table.blockSignals(True)

        # Update table
        self.projects_table.setRowCount(len(projects))

        row_to_select = None
        for row, project in enumerate(projects):
            # Project name
            name_item = QTableWidgetItem(project.name)
            name_item.setData(Qt.ItemDataRole.UserRole, project.id)
            self.projects_table.setItem(row, 0, name_item)

            # Object
            self.projects_table.setItem(row, 1, QTableWidgetItem(project.object_name))

            # Year
            year_text = str(project.year) if project.year else ""
            self.projects_table.setItem(row, 2, QTableWidgetItem(year_text))

            # Status - with color coding
            status_item = QTableWidgetItem(project.status.title())
            # Color code based on status
            if project.status == 'active':
                status_item.setForeground(QBrush(QColor("#0078d4")))  # Blue
            elif project.status == 'completed':
                status_item.setForeground(QBrush(QColor("#107c10")))  # Green
            elif project.status == 'archived':
                status_item.setForeground(QBrush(QColor("#888888")))  # Gray
            self.projects_table.setItem(row, 3, status_item)

            # Created date
            created = project.created_at[:10] if project.created_at else ""
            self.projects_table.setItem(row, 4, QTableWidgetItem(created))

            # Check if this is the previously selected project
            if previously_selected_id is not None and project.id == previously_selected_id:
                row_to_select = row

        # Re-enable signals
        self.projects_table.blockSignals(False)

        # Update unassigned sessions warning
        unassigned = self.project_manager.get_unassigned_sessions()
        if unassigned:
            self.unassigned_label.setText(
                f"⚠️ {len(unassigned)} unassigned sessions"
            )
        else:
            self.unassigned_label.setText("")

        # Restore selection if the previously selected project is still in the list
        if row_to_select is not None:
            self.projects_table.selectRow(row_to_select)
            self.show_project_details(previously_selected_id)
        else:
            # Clear selection if previously selected project is no longer visible
            self.clear_project_details()

    def on_project_selected(self):
        """Handle project selection."""
        selected_rows = self.projects_table.selectedItems()
        if not selected_rows:
            self.clear_project_details()
            self.edit_project_btn.setEnabled(False)
            return

        # Get project ID from first column
        project_id = self.projects_table.item(
            selected_rows[0].row(), 0
        ).data(Qt.ItemDataRole.UserRole)

        self.edit_project_btn.setEnabled(True)
        self.show_project_details(project_id)

    def show_project_details(self, project_id: int):
        """
        Show details for a project.

        Args:
            project_id: Project ID
        """
        self.selected_project_id = project_id

        # Load project
        project = self.project_manager.get_project(project_id)
        if not project:
            return

        # Update info label
        info_html = f"<h3>{project.name}</h3>"
        info_html += f"<p><b>Object:</b> {project.object_name}</p>"
        if project.description:
            info_html += f"<p><b>Description:</b> {project.description}</p>"
        if project.year:
            info_html += f"<p><b>Year:</b> {project.year}</p>"
        info_html += f"<p><b>Status:</b> {project.status.title()}</p>"

        self.info_label.setText(info_html)

        # Load and display filter goals
        goals = self.project_manager.get_filter_goals(project_id)
        self.display_filter_goals(goals)

        # Generate next steps
        self.display_next_steps(project, goals)

        # Show action buttons
        self.mark_complete_btn.setVisible(project.status == 'active')
        self.archive_btn.setVisible(project.status in ['active', 'completed'])
        self.delete_btn.setVisible(True)

    def display_filter_goals(self, goals: list[FilterGoalProgress]):
        """
        Display filter goals in a compact table format.

        Args:
            goals: List of FilterGoalProgress objects
        """
        # Clear existing widgets
        for i in reversed(range(self.goals_layout.count())):
            widget = self.goals_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        if not goals:
            self.goals_group.setVisible(False)
            return

        self.goals_group.setVisible(True)

        # Create table
        goals_table = QTableWidget()
        goals_table.setRowCount(len(goals))
        goals_table.setColumnCount(4)
        goals_table.setHorizontalHeaderLabels(["Filter", "Total", "Approved", "Progress"])

        # Configure table appearance - make columns resizable
        goals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        goals_table.horizontalHeader().setStretchLastSection(False)

        # Restore saved column widths or use defaults
        default_widths = [80, 120, 120, 80]  # Filter, Total, Approved, Progress
        for col in range(4):
            saved_width = self.settings.value(f'projects_goals_table_col_{col}')
            if saved_width:
                goals_table.setColumnWidth(col, int(saved_width))
            else:
                goals_table.setColumnWidth(col, default_widths[col])

        # Connect column resize to save settings
        goals_table.horizontalHeader().sectionResized.connect(self.save_goals_table_column_widths)

        goals_table.verticalHeader().setVisible(False)
        goals_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        goals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        goals_table.setShowGrid(True)

        # Set compact row height
        goals_table.verticalHeader().setDefaultSectionSize(30)

        # Populate table
        for row, goal in enumerate(goals):
            # Filter name
            filter_item = QTableWidgetItem(goal.filter)
            goals_table.setItem(row, 0, filter_item)

            # Total frames with percentage
            total_percentage = min(100, (goal.total_count * 100 // goal.target_count) if goal.target_count > 0 else 0)
            total_item = QTableWidgetItem(f"{goal.total_count}/{goal.target_count} ({total_percentage}%)")
            goals_table.setItem(row, 1, total_item)

            # Approved frames with percentage
            approved_percentage = min(100, (goal.approved_count * 100 // goal.target_count) if goal.target_count > 0 else 0)
            approved_item = QTableWidgetItem(f"{goal.approved_count}/{goal.target_count} ({approved_percentage}%)")
            goals_table.setItem(row, 2, approved_item)

            # Progress indicator with colored circle
            if approved_percentage >= 100:
                # Complete - green circle
                progress_text = "● 100%"
                color = "#5cb85c"  # Green
            elif approved_percentage >= 75:
                # Good progress - light green
                progress_text = f"● {approved_percentage}%"
                color = "#92d050"  # Light green
            elif approved_percentage >= 50:
                # Moderate progress - yellow/orange
                progress_text = f"● {approved_percentage}%"
                color = "#f0ad4e"  # Orange
            elif approved_percentage >= 25:
                # Low progress - orange/red
                progress_text = f"● {approved_percentage}%"
                color = "#e67e22"  # Dark orange
            else:
                # Very low progress - red
                progress_text = f"● {approved_percentage}%"
                color = "#d9534f"  # Red

            progress_item = QTableWidgetItem(progress_text)
            progress_item.setForeground(QBrush(QColor(color)))
            font = progress_item.font()
            font.setBold(True)
            progress_item.setFont(font)
            goals_table.setItem(row, 3, progress_item)

        # Set reasonable height based on content
        table_height = goals_table.horizontalHeader().height() + (len(goals) * 30) + 10
        goals_table.setMaximumHeight(table_height)
        goals_table.setMinimumHeight(table_height)

        # Store reference to keep signal connection alive
        self.current_goals_table = goals_table
        self.goals_layout.addWidget(goals_table)

    def display_next_steps(self, project: Project, goals: list[FilterGoalProgress]):
        """
        Display next steps / recommendations.

        Args:
            project: Project object
            goals: List of FilterGoalProgress objects
        """
        if not goals:
            self.next_steps_group.setVisible(False)
            return

        self.next_steps_group.setVisible(True)

        steps_html = "<ul>"

        # Check what's needed
        needs_frames = []
        needs_grading = []
        needs_more_approved = []

        for goal in goals:
            if goal.total_count < goal.target_count:
                needs_frames.append(
                    f"{goal.filter}: {goal.remaining} more frames"
                )
            if goal.total_count > goal.approved_count and goal.total_count > 0:
                ungraded = goal.total_count - goal.approved_count - (goal.total_count - goal.approved_count)
                needs_grading.append(f"{goal.filter}")
            if goal.approved_count < goal.target_count:
                needs_more_approved.append(
                    f"{goal.filter}: {goal.approved_remaining} more approved"
                )

        if needs_frames:
            steps_html += "<li><b>Capture more frames:</b><ul>"
            for item in needs_frames:
                steps_html += f"<li>{item}</li>"
            steps_html += "</ul></li>"

        if needs_grading:
            steps_html += "<li><b>Grade frames in PixInsight SubFrame Selector</b></li>"
            steps_html += "<li><b>Import quality data CSV</b></li>"

        if needs_more_approved and not needs_frames:
            steps_html += "<li><b>Capture additional frames to reach approved target:</b><ul>"
            for item in needs_more_approved:
                steps_html += f"<li>{item}</li>"
            steps_html += "</ul></li>"

        # Check if all goals met
        all_complete = all(
            goal.approved_count >= goal.target_count for goal in goals
        )
        if all_complete:
            steps_html += "<li><b>✓ All goals met!</b> Ready to generate WBPP file lists</li>"

        steps_html += "</ul>"

        self.next_steps_text.setHtml(steps_html)

    def clear_project_details(self):
        """Clear project details panel."""
        self.selected_project_id = None
        self.info_label.setText("Select a project to view details")
        self.goals_group.setVisible(False)
        self.next_steps_group.setVisible(False)
        self.mark_complete_btn.setVisible(False)
        self.archive_btn.setVisible(False)
        self.delete_btn.setVisible(False)

    def create_new_project(self):
        """Open dialog to create a new project."""
        dialog = NewProjectDialog(self.db_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_projects()

    def edit_project(self):
        """Open dialog to edit the selected project."""
        if not self.selected_project_id:
            return

        # Get project details
        project = self.project_manager.get_project(self.selected_project_id)
        if not project:
            QMessageBox.warning(self, "Error", "Project not found.")
            return

        # Create edit dialog
        from ui.edit_project_dialog import EditProjectDialog
        dialog = EditProjectDialog(self.db_path, project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_projects()
            # Restore selection to the edited project
            if self.selected_project_id:
                self.show_project_details(self.selected_project_id)

    def mark_project_complete(self):
        """Mark selected project as complete."""
        if not self.selected_project_id:
            return

        reply = QMessageBox.question(
            self,
            "Mark Complete",
            "Mark this project as completed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.project_manager.update_project_status(
                self.selected_project_id, "completed"
            )
            self.refresh_projects()

    def archive_project(self):
        """Archive selected project."""
        if not self.selected_project_id:
            return

        reply = QMessageBox.question(
            self,
            "Archive Project",
            "Archive this project? It will be hidden from the active list.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.project_manager.update_project_status(
                self.selected_project_id, "archived"
            )
            self.refresh_projects()

    def delete_project(self):
        """Delete selected project."""
        if not self.selected_project_id:
            return

        project = self.project_manager.get_project(self.selected_project_id)
        if not project:
            return

        reply = QMessageBox.warning(
            self,
            "Delete Project",
            f"Are you sure you want to delete '{project.name}'?\n\n"
            "This will:\n"
            "- Remove the project and all its data\n"
            "- Unlink all frames from this project\n"
            "- This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.project_manager.delete_project(self.selected_project_id)
                QMessageBox.information(
                    self, "Success", f"Project '{project.name}' deleted."
                )
                self.refresh_projects()
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to delete project:\n{str(e)}"
                )

    def import_quality_data(self):
        """Import quality data from PixInsight SubFrame Selector CSV."""
        # Select CSV file
        csv_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SubFrame Selector CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not csv_path:
            return

        try:
            # Import CSV
            importer = SubFrameSelectorImporter(self.db_path)
            stats = importer.import_csv(csv_path, approval_column="Approved")

            # Show results
            result_msg = (
                f"Quality data import completed!\n\n"
                f"Total frames in CSV: {stats['total_csv_frames']}\n"
                f"Matched in database: {stats['matched']}\n"
                f"Not found: {stats['not_found']}\n\n"
                f"Approval Status:\n"
                f"  Approved: {stats['approved']}\n"
                f"  Rejected: {stats['rejected']}\n"
                f"  Not graded: {stats['not_graded']}\n\n"
                f"Updated projects: {stats['updated_projects']}"
            )

            QMessageBox.information(self, "Import Complete", result_msg)

            # Refresh to show updated progress
            self.refresh_projects()
            if self.selected_project_id:
                self.show_project_details(self.selected_project_id)

        except FileNotFoundError as e:
            QMessageBox.critical(self, "File Not Found", str(e))
        except ValueError as e:
            QMessageBox.critical(self, "Invalid CSV", str(e))
        except Exception as e:
            QMessageBox.critical(
                self, "Import Failed", f"Failed to import quality data:\n{str(e)}"
            )

    def save_splitter_state(self) -> None:
        """Save the splitter sizes to settings."""
        sizes = self.projects_splitter.sizes()
        self.settings.setValue('projects_splitter_sizes', sizes)

        # Also save the details content splitter state
        self.save_details_content_splitter_state()

    def restore_splitter_state(self) -> None:
        """Restore the splitter sizes from settings."""
        saved_sizes = self.settings.value('projects_splitter_sizes')
        if saved_sizes:
            # Convert to integers (QSettings may return strings)
            sizes = [int(s) for s in saved_sizes]
            self.projects_splitter.setSizes(sizes)

        # Also restore the details content splitter state
        self.restore_details_content_splitter_state()

    def save_details_content_splitter_state(self) -> None:
        """Save the details content splitter sizes to settings."""
        sizes = self.details_content_splitter.sizes()
        self.settings.setValue('projects_details_content_splitter_sizes', sizes)

    def restore_details_content_splitter_state(self) -> None:
        """Restore the details content splitter sizes from settings."""
        saved_sizes = self.settings.value('projects_details_content_splitter_sizes')
        if saved_sizes:
            # Convert to integers (QSettings may return strings)
            sizes = [int(s) for s in saved_sizes]
            self.details_content_splitter.setSizes(sizes)

    def save_goals_table_column_widths(self) -> None:
        """Save the goals table column widths to settings."""
        if self.current_goals_table:
            for col in range(self.current_goals_table.columnCount()):
                width = self.current_goals_table.columnWidth(col)
                self.settings.setValue(f'projects_goals_table_col_{col}', width)

    def save_projects_table_column_widths(self) -> None:
        """Save the projects table column widths to settings."""
        for col in range(self.projects_table.columnCount()):
            width = self.projects_table.columnWidth(col)
            self.settings.setValue(f'projects_table_col_{col}', width)
