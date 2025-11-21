#!/usr/bin/env python3
"""
Fix Filter Names - Update project filter goals to match actual frame filters

This script helps when filter names in project goals don't match actual frame filters.
For example, when template uses 'L' but frames use 'Luminance'.
"""

import sqlite3
import sys
from pathlib import Path


def fix_filter_names(db_path, project_id):
    """Fix filter name mismatches for a specific project."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get project info
        cursor.execute('SELECT name, object_name FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        if not row:
            print(f"✗ Project {project_id} not found!")
            return

        project_name, object_name = row
        print(f"Project: {project_name}")
        print(f"Object: {object_name}")
        print("=" * 60)

        # Get actual filters used in frames
        cursor.execute('''
            SELECT DISTINCT filter
            FROM xisf_files
            WHERE object = ? AND imagetyp LIKE '%Light%'
            ORDER BY filter
        ''', (object_name,))

        actual_filters = [row[0] for row in cursor.fetchall()]
        print(f"\nActual filters in frames: {actual_filters}")

        # Get current filter goals
        cursor.execute('''
            SELECT id, filter, target_count, total_count
            FROM project_filter_goals
            WHERE project_id = ?
        ''', (project_id,))

        goals = cursor.fetchall()
        print(f"\nCurrent filter goals:")
        for goal_id, filter_name, target, total in goals:
            print(f"  {filter_name}: target={target}, total={total}")

        # Common filter mappings
        mappings = {
            'L': 'Luminance',
            'R': 'Red',
            'G': 'Green',
            'B': 'Blue',
            'Ha': 'Hydrogen Alpha',
            'OIII': 'Oxygen III',
            'SII': 'Sulfur II'
        }

        print(f"\n{'Proposed Changes':-^60}")

        changes = []
        for goal_id, filter_name, target, total in goals:
            # Check if there's a common mapping
            if filter_name in mappings:
                expanded = mappings[filter_name]
                if expanded in actual_filters:
                    changes.append((goal_id, filter_name, expanded))
                    print(f"  '{filter_name}' → '{expanded}'")

            # Check reverse mapping
            reverse_mappings = {v: k for k, v in mappings.items()}
            if filter_name in reverse_mappings:
                shortened = reverse_mappings[filter_name]
                if shortened in actual_filters:
                    changes.append((goal_id, filter_name, shortened))
                    print(f"  '{filter_name}' → '{shortened}'")

        if not changes:
            print("  No automatic mappings found!")
            print("\n⚠️  Manual intervention needed:")
            print("  You may need to:")
            print("  1. Recreate the project with correct filter names, OR")
            print("  2. Standardize filter names in your frames, OR")
            print("  3. Manually update filter goals in the database")
            return

        # Ask for confirmation
        print("\n" + "=" * 60)
        response = input("Apply these changes? (yes/no): ").strip().lower()

        if response != 'yes':
            print("✗ Changes cancelled")
            return

        # Apply changes
        print("\nApplying changes...")
        for goal_id, old_name, new_name in changes:
            cursor.execute('''
                UPDATE project_filter_goals
                SET filter = ?
                WHERE id = ?
            ''', (new_name, goal_id))
            print(f"  ✓ Updated: '{old_name}' → '{new_name}'")

        # Recalculate counts
        print("\nRecalculating frame counts...")
        sys.path.insert(0, str(Path(__file__).parent))
        from core.project_manager import ProjectManager
        pm = ProjectManager(db_path)
        pm.recalculate_project_counts(project_id)

        # Show final results
        cursor.execute('''
            SELECT filter, target_count, total_count, approved_count
            FROM project_filter_goals
            WHERE project_id = ?
        ''', (project_id,))

        print("\nFinal filter goals:")
        for filter_name, target, total, approved in cursor.fetchall():
            print(f"  {filter_name}: target={target}, total={total}, approved={approved}")

        conn.commit()
        print("\n✓ Filter names updated successfully!")
        print("\nRefresh the Projects tab in AstroFileManager to see the changes.")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        conn.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: python fix_filter_names.py <db_path> <project_id>")
        print("Example: python fix_filter_names.py xisf_catalog.db 1")
        sys.exit(1)

    db_path = sys.argv[1]
    project_id = int(sys.argv[2])

    if not Path(db_path).exists():
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)

    fix_filter_names(db_path, project_id)


if __name__ == "__main__":
    main()
