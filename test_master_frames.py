#!/usr/bin/env python3
"""
Test script for master frames functionality.

This script tests the master frames import and display functionality
without requiring a full GUI.
"""

import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.project_manager import ProjectManager, MasterFrame


def test_master_frames(db_path='xisf_catalog.db'):
    """
    Test master frames functionality.

    Args:
        db_path: Path to the database file
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        print("Please create a database first using create_db.py")
        return False

    print(f"Testing master frames functionality with: {db_path}")
    print("-" * 60)

    try:
        # Check if project_master_frames table exists
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='project_master_frames'
        """)

        if not cursor.fetchone():
            print("❌ Table 'project_master_frames' does not exist")
            print("   Run migration: python migrate_add_project_master_frames.py")
            conn.close()
            return False

        print("✓ Table 'project_master_frames' exists")

        # Check table structure
        cursor.execute("PRAGMA table_info(project_master_frames)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            'id': 'INTEGER',
            'project_id': 'INTEGER',
            'file_id': 'INTEGER',
            'frame_type': 'TEXT',
            'filter': 'TEXT',
            'exposure': 'REAL',
            'ccd_temp': 'REAL',
            'binning': 'TEXT',
            'imported_date': 'TEXT',
            'notes': 'TEXT'
        }

        print("\nChecking table columns:")
        all_columns_present = True
        for col_name, col_type in expected_columns.items():
            if col_name in columns:
                print(f"  ✓ {col_name} ({col_type})")
            else:
                print(f"  ❌ Missing column: {col_name}")
                all_columns_present = False

        if not all_columns_present:
            conn.close()
            return False

        # Check for projects
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        print(f"\n✓ Database has {project_count} project(s)")

        # Check for master frames in xisf_files
        cursor.execute("""
            SELECT COUNT(*) FROM xisf_files
            WHERE imagetyp LIKE '%Master%'
        """)
        master_count = cursor.fetchone()[0]
        print(f"✓ Database has {master_count} master frame(s) in catalog")

        conn.close()

        # Test ProjectManager methods
        print("\nTesting ProjectManager methods:")
        pm = ProjectManager(db_path)

        # Test get_master_frames (should work even if no frames imported)
        if project_count > 0:
            cursor = sqlite3.connect(db_path).cursor()
            cursor.execute("SELECT id, name FROM projects LIMIT 1")
            project_id, project_name = cursor.fetchone()
            cursor.close()

            print(f"\n  Testing with project: {project_name} (ID: {project_id})")

            master_frames = pm.get_master_frames(project_id)
            print(f"  ✓ get_master_frames() returned {len(master_frames)} frame(s)")

            summary = pm.get_master_frames_summary(project_id)
            print(f"  ✓ get_master_frames_summary() returned: {summary}")

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        print("\nThe master frames feature is ready to use.")
        print("\nNext steps:")
        print("1. Launch the application: python AstroFileManager.py")
        print("2. Select a project in the Projects tab")
        print("3. Click 'Import Master Frames' button")
        print("4. Select master frames to import")
        print("5. View imported frames in the project details")

        return True

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for test script."""
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'

    # Run tests
    success = test_master_frames(db_path)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
