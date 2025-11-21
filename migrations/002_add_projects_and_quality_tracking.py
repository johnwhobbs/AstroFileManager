#!/usr/bin/env python3
"""
Database Migration: Add Projects and Quality Tracking

Creates project-based workflow for tracking imaging campaigns across multiple
sessions and nights, with integrated quality metrics from PixInsight SubFrame Selector.

Tables Created:
- projects: Imaging campaign tracking (e.g., "M31 Narrowband 2024")
- project_filter_goals: Target frame counts per filter
- project_sessions: Links sessions to projects

Columns Added to xisf_files:
- project_id: Links frames to projects
- session_assignment_id: Links frames to project_sessions
- Quality metrics: fwhm, eccentricity, snr, star_count, background_level
- approval_status, grading_date, grading_notes
"""

import sqlite3
import sys
from pathlib import Path


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def apply_migration(db_path: str):
    """Apply migration to add projects and quality tracking."""
    print(f"Applying migration to: {db_path}")
    print("=" * 60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ========== Create projects table ==========
        if not table_exists(cursor, 'projects'):
            print("\nCreating 'projects' table...")
            cursor.execute('''
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    object_name TEXT NOT NULL,
                    description TEXT,
                    year INTEGER,
                    start_date TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✓ Created 'projects' table")
        else:
            print("\n'projects' table already exists (skipping)")

        # ========== Create project_filter_goals table ==========
        if not table_exists(cursor, 'project_filter_goals'):
            print("\nCreating 'project_filter_goals' table...")
            cursor.execute('''
                CREATE TABLE project_filter_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    filter TEXT NOT NULL,
                    target_count INTEGER NOT NULL,
                    total_count INTEGER DEFAULT 0,
                    approved_count INTEGER DEFAULT 0,
                    last_updated TEXT,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, filter)
                )
            ''')
            print("✓ Created 'project_filter_goals' table")
        else:
            print("\n'project_filter_goals' table already exists (skipping)")

        # ========== Create project_sessions table ==========
        if not table_exists(cursor, 'project_sessions'):
            print("\nCreating 'project_sessions' table...")
            cursor.execute('''
                CREATE TABLE project_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    date_loc TEXT NOT NULL,
                    object_name TEXT,
                    filter TEXT,
                    frame_count INTEGER DEFAULT 0,
                    approved_count INTEGER DEFAULT 0,
                    rejected_count INTEGER DEFAULT 0,
                    graded INTEGER DEFAULT 0,
                    avg_fwhm REAL,
                    notes TEXT,
                    assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, session_id)
                )
            ''')
            print("✓ Created 'project_sessions' table")
        else:
            print("\n'project_sessions' table already exists (skipping)")

        # ========== Add columns to xisf_files ==========
        print("\nAdding columns to 'xisf_files' table...")

        columns_to_add = [
            ("project_id", "INTEGER"),
            ("session_assignment_id", "INTEGER"),
            ("fwhm", "REAL"),
            ("eccentricity", "REAL"),
            ("snr", "REAL"),
            ("star_count", "INTEGER"),
            ("background_level", "REAL"),
            ("approval_status", "TEXT DEFAULT 'not_graded'"),
            ("grading_date", "TEXT"),
            ("grading_notes", "TEXT"),
        ]

        added_columns = []
        for col_name, col_type in columns_to_add:
            if not column_exists(cursor, 'xisf_files', col_name):
                cursor.execute(f"ALTER TABLE xisf_files ADD COLUMN {col_name} {col_type}")
                added_columns.append(col_name)
                print(f"  ✓ Added column: {col_name}")
            else:
                print(f"  • Column already exists: {col_name} (skipping)")

        # ========== Create indexes ==========
        print("\nCreating indexes...")

        indexes = [
            ("idx_project_id", "CREATE INDEX IF NOT EXISTS idx_project_id ON xisf_files(project_id)"),
            ("idx_session_assignment_id", "CREATE INDEX IF NOT EXISTS idx_session_assignment_id ON xisf_files(session_assignment_id)"),
            ("idx_approval_status", "CREATE INDEX IF NOT EXISTS idx_approval_status ON xisf_files(approval_status)"),
            ("idx_fwhm", "CREATE INDEX IF NOT EXISTS idx_fwhm ON xisf_files(fwhm)"),
        ]

        for index_name, index_sql in indexes:
            cursor.execute(index_sql)
            print(f"  ✓ Created index: {index_name}")

        # ========== Set defaults for existing records ==========
        if 'approval_status' in added_columns:
            print("\nSetting default approval_status for existing records...")
            cursor.execute("""
                UPDATE xisf_files
                SET approval_status = 'not_graded'
                WHERE approval_status IS NULL
            """)
            updated = cursor.rowcount
            print(f"  ✓ Updated {updated} records")

        conn.commit()

        # ========== Migration Summary ==========
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

        # Show statistics
        cursor.execute("SELECT COUNT(*) FROM xisf_files")
        total_files = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM xisf_files WHERE project_id IS NOT NULL")
        assigned_files = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM xisf_files WHERE approval_status = 'not_graded'")
        not_graded = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM xisf_files WHERE approval_status = 'approved'")
        approved = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM xisf_files WHERE approval_status = 'rejected'")
        rejected = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]

        print(f"\nDatabase Summary:")
        print(f"  Total files: {total_files}")
        print(f"  Files assigned to projects: {assigned_files}")
        print(f"  Projects: {project_count}")
        print(f"\nGrading Status:")
        print(f"  Not graded: {not_graded}")
        print(f"  Approved: {approved}")
        print(f"  Rejected: {rejected}")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


def verify_migration(db_path: str) -> bool:
    """Verify that migration was applied successfully."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check tables exist
        required_tables = ['projects', 'project_filter_goals', 'project_sessions']
        for table in required_tables:
            if not table_exists(cursor, table):
                print(f"✗ Verification failed: Missing table '{table}'")
                return False

        # Check columns exist
        required_columns = [
            'project_id', 'session_assignment_id', 'fwhm', 'eccentricity',
            'snr', 'star_count', 'background_level', 'approval_status',
            'grading_date', 'grading_notes'
        ]
        for column in required_columns:
            if not column_exists(cursor, 'xisf_files', column):
                print(f"✗ Verification failed: Missing column '{column}' in xisf_files")
                return False

        print("\n✓ Migration verification passed!")
        return True

    finally:
        conn.close()


def main():
    """Main entry point for migration script."""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'

    # Check if database exists
    if not Path(db_path).exists():
        print(f"✗ Error: Database not found at {db_path}")
        print("Please create the database first using create_db.py")
        sys.exit(1)

    # Apply migration
    apply_migration(db_path)

    # Verify migration
    if verify_migration(db_path):
        print("\n✓ Migration 002_add_projects_and_quality_tracking completed successfully!")
    else:
        print("\n✗ Migration verification failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
