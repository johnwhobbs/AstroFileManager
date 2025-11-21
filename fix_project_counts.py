#!/usr/bin/env python3
"""
Fix Project Counts - Recalculates frame counts for all projects

Use this script after the NULL-safe filter comparison bug fix to update
existing projects that show 0 frames.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path so we can import project_manager
sys.path.insert(0, str(Path(__file__).parent))

from core.project_manager import ProjectManager


def fix_all_projects(db_path):
    """Recalculate counts for all projects."""
    print(f"Fixing project counts in: {db_path}")
    print("=" * 60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all projects
        cursor.execute('SELECT id, name FROM projects ORDER BY id')
        projects = cursor.fetchall()

        if not projects:
            print("\nNo projects found in database.")
            return

        print(f"\nFound {len(projects)} project(s):\n")

        pm = ProjectManager(db_path)

        for project_id, project_name in projects:
            print(f"Project {project_id}: {project_name}")

            # Show before counts
            cursor.execute('''
                SELECT filter, total_count, approved_count
                FROM project_filter_goals
                WHERE project_id = ?
            ''', (project_id,))

            goals_before = cursor.fetchall()
            print("  Before:")
            for filter_name, total, approved in goals_before:
                print(f"    {filter_name}: total={total}, approved={approved}")

            # Recalculate
            pm.recalculate_project_counts(project_id)

            # Show after counts
            cursor.execute('''
                SELECT filter, total_count, approved_count
                FROM project_filter_goals
                WHERE project_id = ?
            ''', (project_id,))

            goals_after = cursor.fetchall()
            print("  After:")
            for filter_name, total, approved in goals_after:
                print(f"    {filter_name}: total={total}, approved={approved}")

            print()

        print("=" * 60)
        print("✓ All project counts have been recalculated!")
        print("\nYou can now refresh the Projects tab in AstroFileManager.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        conn.close()


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'

    if not Path(db_path).exists():
        print(f"✗ Database not found: {db_path}")
        print("\nUsage: python fix_project_counts.py [database_path]")
        print("Example: python fix_project_counts.py xisf_catalog.db")
        sys.exit(1)

    fix_all_projects(db_path)


if __name__ == "__main__":
    main()
