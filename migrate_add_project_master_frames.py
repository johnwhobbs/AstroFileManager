#!/usr/bin/env python3
"""
Migration script to add project_master_frames table.

This script creates a new table to track master frames (Master Dark, Master Flat,
Master Bias) that are imported to projects after pre-processing/stacking is complete.

Usage:
    python migrate_add_project_master_frames.py [database_path]

If no database path is provided, defaults to 'xisf_catalog.db'
"""

import sqlite3
import sys
import os


def migrate_database(db_path='xisf_catalog.db'):
    """
    Add project_master_frames table for tracking imported master calibration frames.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        return False

    print(f"Migrating database: {db_path}")
    print("-" * 60)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if projects table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='projects'
        """)
        if not cursor.fetchone():
            print("Error: 'projects' table does not exist.")
            print("Please ensure the database schema is up to date.")
            conn.close()
            return False

        print("✓ Database has 'projects' table")

        # Check if project_master_frames table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='project_master_frames'
        """)
        if cursor.fetchone():
            print("✓ Table 'project_master_frames' already exists")
            print("\nMigration already applied - no changes needed.")
            conn.close()
            return True

        # Create project_master_frames table
        print("\nCreating project_master_frames table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_master_frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                file_id INTEGER NOT NULL,
                frame_type TEXT NOT NULL,
                filter TEXT,
                exposure REAL,
                ccd_temp REAL,
                binning TEXT,
                imported_date TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(file_id) REFERENCES xisf_files(id) ON DELETE CASCADE,
                UNIQUE(project_id, file_id)
            )
        ''')
        print("  ✓ Created project_master_frames table")

        # Create indexes for efficient querying
        print("\nCreating indexes for project_master_frames table...")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project_master_frames_project_id
            ON project_master_frames(project_id)
        ''')
        print("  ✓ Created idx_project_master_frames_project_id")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project_master_frames_file_id
            ON project_master_frames(file_id)
        ''')
        print("  ✓ Created idx_project_master_frames_file_id")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project_master_frames_type_filter
            ON project_master_frames(project_id, frame_type, filter)
        ''')
        print("  ✓ Created idx_project_master_frames_type_filter")

        # Commit changes
        conn.commit()
        conn.close()

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print("\nThe project_master_frames table has been created.")
        print("You can now import and track master calibration frames")
        print("(Master Dark, Master Flat, Master Bias) for each project.")

        return True

    except sqlite3.Error as e:
        print(f"\nError during migration: {e}")
        return False


def main():
    """Main entry point for migration script."""
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'

    # Run migration
    success = migrate_database(db_path)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
