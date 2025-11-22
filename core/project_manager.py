"""
Project Manager for AstroFileManager

Handles database operations for project-based workflow tracking.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Project:
    """Represents an imaging project."""
    id: Optional[int]
    name: str
    object_name: str
    description: Optional[str]
    year: Optional[int]
    start_date: Optional[str]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class FilterGoalProgress:
    """Represents progress toward a filter goal."""
    filter: str
    target_count: int
    total_count: int
    approved_count: int
    remaining: int
    approved_remaining: int


class ProjectManager:
    """Manages project-related database operations."""

    def __init__(self, db_path: str):
        """
        Initialize ProjectManager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def create_project(
        self,
        name: str,
        object_name: str,
        filter_goals: Dict[str, int],
        description: Optional[str] = None,
        year: Optional[int] = None,
        start_date: Optional[str] = None
    ) -> int:
        """
        Create a new project with filter goals.

        Args:
            name: Project name (must be unique)
            object_name: Object being imaged
            filter_goals: Dict mapping filter names to target counts
            description: Optional project description
            year: Optional year (for reference only)
            start_date: Optional start date

        Returns:
            Project ID

        Raises:
            sqlite3.IntegrityError: If project name already exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Insert project
            cursor.execute('''
                INSERT INTO projects (name, object_name, description, year, start_date, status)
                VALUES (?, ?, ?, ?, ?, 'active')
            ''', (name, object_name, description, year, start_date))

            project_id = cursor.lastrowid

            # Insert filter goals
            for filter_name, target_count in filter_goals.items():
                cursor.execute('''
                    INSERT INTO project_filter_goals (project_id, filter, target_count)
                    VALUES (?, ?, ?)
                ''', (project_id, filter_name, target_count))

            conn.commit()
            return project_id

        finally:
            conn.close()

    def get_project(self, project_id: int) -> Optional[Project]:
        """
        Get project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project object or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, name, object_name, description, year, start_date,
                       status, created_at, updated_at
                FROM projects
                WHERE id = ?
            ''', (project_id,))

            row = cursor.fetchone()
            if row:
                return Project(*row)
            return None

        finally:
            conn.close()

    def list_projects(self, status: Optional[str] = None) -> List[Project]:
        """
        List all projects.

        Args:
            status: Optional filter by status ('active', 'completed', 'archived')

        Returns:
            List of Project objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if status:
                cursor.execute('''
                    SELECT id, name, object_name, description, year, start_date,
                           status, created_at, updated_at
                    FROM projects
                    WHERE status = ?
                    ORDER BY created_at DESC
                ''', (status,))
            else:
                cursor.execute('''
                    SELECT id, name, object_name, description, year, start_date,
                           status, created_at, updated_at
                    FROM projects
                    ORDER BY created_at DESC
                ''')

            return [Project(*row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_filter_goals(self, project_id: int) -> List[FilterGoalProgress]:
        """
        Get filter goals and progress for a project.

        Args:
            project_id: Project ID

        Returns:
            List of FilterGoalProgress objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT filter, target_count, total_count, approved_count
                FROM project_filter_goals
                WHERE project_id = ?
                ORDER BY filter
            ''', (project_id,))

            goals = []
            for filter_name, target, total, approved in cursor.fetchall():
                goals.append(FilterGoalProgress(
                    filter=filter_name,
                    target_count=target,
                    total_count=total,
                    approved_count=approved,
                    remaining=max(0, target - total),
                    approved_remaining=max(0, target - approved)
                ))

            return goals

        finally:
            conn.close()

    def assign_session_to_project(
        self,
        project_id: int,
        session_id: str,
        date_loc: str,
        object_name: str,
        filter_name: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Assign a session to a project.

        Args:
            project_id: Project ID
            session_id: Session identifier (e.g., "2024-11-15_M31_Ha")
            date_loc: Session date
            object_name: Object name
            filter_name: Optional filter name
            notes: Optional notes

        Returns:
            Session assignment ID

        Raises:
            sqlite3.IntegrityError: If session already assigned to this project
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get frame count for this session
            cursor.execute('''
                SELECT COUNT(*)
                FROM xisf_files
                WHERE date_loc = ? AND object = ? AND imagetyp LIKE '%Light%'
                AND (? IS NULL OR filter = ?)
            ''', (date_loc, object_name, filter_name, filter_name))

            frame_count = cursor.fetchone()[0]

            # Insert session assignment
            cursor.execute('''
                INSERT INTO project_sessions
                (project_id, session_id, date_loc, object_name, filter, frame_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (project_id, session_id, date_loc, object_name, filter_name, frame_count))

            assignment_id = cursor.lastrowid

            # Update xisf_files to link frames to project
            cursor.execute('''
                UPDATE xisf_files
                SET project_id = ?, session_assignment_id = ?
                WHERE date_loc = ? AND object = ? AND imagetyp LIKE '%Light%'
                AND (? IS NULL OR filter = ?)
            ''', (project_id, assignment_id, date_loc, object_name, filter_name, filter_name))

            # Update filter goal counts
            self._update_filter_goal_counts(cursor, project_id)

            conn.commit()
            return assignment_id

        finally:
            conn.close()

    def _update_filter_goal_counts(self, cursor, project_id: int):
        """
        Update filter goal counts for a project.

        Args:
            cursor: SQLite cursor
            project_id: Project ID
        """
        # Update total_count and approved_count for each filter
        # Use COALESCE for NULL-safe filter comparison
        cursor.execute('''
            UPDATE project_filter_goals
            SET
                total_count = (
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE project_id = ?
                    AND COALESCE(filter, '') = COALESCE(project_filter_goals.filter, '')
                ),
                approved_count = (
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE project_id = ?
                    AND COALESCE(filter, '') = COALESCE(project_filter_goals.filter, '')
                    AND approval_status = 'approved'
                ),
                last_updated = CURRENT_TIMESTAMP
            WHERE project_id = ?
        ''', (project_id, project_id, project_id))

    def recalculate_project_counts(self, project_id: int):
        """
        Manually recalculate filter goal counts for a project.

        Useful for fixing counts after a bug fix or manual database changes.

        Args:
            project_id: Project ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            self._update_filter_goal_counts(cursor, project_id)
            conn.commit()

        finally:
            conn.close()

    def update_project_status(self, project_id: int, status: str):
        """
        Update project status.

        Args:
            project_id: Project ID
            status: New status ('active', 'completed', 'archived')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE projects
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, project_id))

            conn.commit()

        finally:
            conn.close()

    def update_project(self, project_id: int, name: str, object_name: str,
                      year: Optional[int] = None, description: Optional[str] = None):
        """
        Update project details.

        Args:
            project_id: Project ID
            name: Project name
            object_name: Object name
            year: Optional year
            description: Optional description
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE projects
                SET name = ?, object_name = ?, year = ?, description = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (name, object_name, year, description, project_id))

            conn.commit()

        finally:
            conn.close()

    def update_filter_goals(self, project_id: int, filter_goals: Dict[str, int]):
        """
        Update filter goals for a project. Removes old goals and adds new ones.

        Args:
            project_id: Project ID
            filter_goals: Dictionary of {filter_name: target_count}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Delete existing filter goals
            cursor.execute('DELETE FROM project_filter_goals WHERE project_id = ?',
                         (project_id,))

            # Insert new filter goals
            for filter_name, target_count in filter_goals.items():
                cursor.execute('''
                    INSERT INTO project_filter_goals
                    (project_id, filter, target_count, total_count, approved_count)
                    VALUES (?, ?, ?, 0, 0)
                ''', (project_id, filter_name, target_count))

            # Recalculate counts based on existing frames
            self._update_filter_goal_counts(cursor, project_id)

            conn.commit()

        finally:
            conn.close()

    def get_project_by_name(self, name: str) -> Optional[Project]:
        """
        Get a project by name.

        Args:
            name: Project name

        Returns:
            Project object or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, name, object_name, description, year, start_date,
                       status, created_at, updated_at
                FROM projects
                WHERE name = ?
            ''', (name,))

            row = cursor.fetchone()
            if row:
                return Project(
                    id=row[0],
                    name=row[1],
                    object_name=row[2],
                    description=row[3],
                    year=row[4],
                    start_date=row[5],
                    status=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
            return None

        finally:
            conn.close()

    def get_unassigned_sessions(self) -> List[Tuple]:
        """
        Get sessions that are not assigned to any project.

        Returns:
            List of tuples (date_loc, object, filter, frame_count)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT
                    date_loc, object, filter,
                    COUNT(*) as frame_count
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
                    AND project_id IS NULL
                    AND date_loc IS NOT NULL
                    AND object IS NOT NULL
                GROUP BY date_loc, object, filter
                ORDER BY date_loc DESC, object, filter
            ''')

            return cursor.fetchall()

        finally:
            conn.close()

    def get_session_assignment(
        self,
        date_loc: str,
        object_name: str,
        filter_name: Optional[str] = None
    ) -> Optional[Tuple[int, int, str]]:
        """
        Check if a session is assigned to a project.

        Args:
            date_loc: Session date
            object_name: Object name
            filter_name: Optional filter name

        Returns:
            Tuple of (project_id, assignment_id, project_name) if assigned, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT ps.project_id, ps.id, p.name
                FROM project_sessions ps
                JOIN projects p ON ps.project_id = p.id
                WHERE ps.date_loc = ?
                AND ps.object_name = ?
                AND (ps.filter = ? OR (ps.filter IS NULL AND ? IS NULL))
            ''', (date_loc, object_name, filter_name, filter_name))

            result = cursor.fetchone()
            return result if result else None

        finally:
            conn.close()

    def unassign_session_from_project(
        self,
        date_loc: str,
        object_name: str,
        filter_name: Optional[str] = None
    ):
        """
        Unassign a session from a project.

        Args:
            date_loc: Session date
            object_name: Object name
            filter_name: Optional filter name
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get the project_id before deleting
            cursor.execute('''
                SELECT project_id
                FROM project_sessions
                WHERE date_loc = ?
                AND object_name = ?
                AND (filter = ? OR (filter IS NULL AND ? IS NULL))
            ''', (date_loc, object_name, filter_name, filter_name))

            result = cursor.fetchone()
            if not result:
                return  # Session not assigned

            project_id = result[0]

            # Delete the session assignment
            cursor.execute('''
                DELETE FROM project_sessions
                WHERE date_loc = ?
                AND object_name = ?
                AND (filter = ? OR (filter IS NULL AND ? IS NULL))
            ''', (date_loc, object_name, filter_name, filter_name))

            # Unlink frames from project
            cursor.execute('''
                UPDATE xisf_files
                SET project_id = NULL, session_assignment_id = NULL
                WHERE date_loc = ?
                AND object = ?
                AND imagetyp LIKE '%Light%'
                AND (filter = ? OR (filter IS NULL AND ? IS NULL))
            ''', (date_loc, object_name, filter_name, filter_name))

            # Update filter goal counts for the project
            self._update_filter_goal_counts(cursor, project_id)

            conn.commit()

        finally:
            conn.close()

    def delete_project(self, project_id: int):
        """
        Delete a project and all related data.

        Args:
            project_id: Project ID

        Note:
            CASCADE deletion will automatically remove:
            - project_filter_goals entries
            - project_sessions entries
            xisf_files project_id will be set to NULL
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Unlink frames from project
            cursor.execute('''
                UPDATE xisf_files
                SET project_id = NULL, session_assignment_id = NULL
                WHERE project_id = ?
            ''', (project_id,))

            # Delete project (CASCADE will handle related tables)
            cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))

            conn.commit()

        finally:
            conn.close()
