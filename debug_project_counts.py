#!/usr/bin/env python3
"""
Debug script to investigate project frame counting issue.
"""

import sqlite3
import sys

def debug_project(db_path, project_id):
    """Debug why a project shows 0 frames."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print(f"Debugging Project ID: {project_id}")
        print("=" * 80)

        # Get project info
        cursor.execute('''
            SELECT name, object_name, status
            FROM projects
            WHERE id = ?
        ''', (project_id,))

        row = cursor.fetchone()
        if not row:
            print(f"✗ Project {project_id} not found!")
            return

        project_name, object_name, status = row
        print(f"\nProject: {project_name}")
        print(f"Object: {object_name}")
        print(f"Status: {status}")

        # Get filter goals
        print(f"\n{'Filter Goals':-^80}")
        cursor.execute('''
            SELECT filter, target_count, total_count, approved_count
            FROM project_filter_goals
            WHERE project_id = ?
        ''', (project_id,))

        goals = cursor.fetchall()
        if goals:
            for filter_name, target, total, approved in goals:
                print(f"  {filter_name}: target={target}, total={total}, approved={approved}")
        else:
            print("  No filter goals found!")

        # Get sessions
        print(f"\n{'Project Sessions':-^80}")
        cursor.execute('''
            SELECT id, session_id, date_loc, filter, frame_count, graded
            FROM project_sessions
            WHERE project_id = ?
        ''', (project_id,))

        sessions = cursor.fetchall()
        if sessions:
            for sess_id, session_id, date_loc, filter_name, frame_count, graded in sessions:
                print(f"  Session {sess_id}: {session_id}")
                print(f"    Date: {date_loc}, Filter: {filter_name}, Frames: {frame_count}, Graded: {graded}")
        else:
            print("  No sessions assigned!")

        # Check actual frames linked to project
        print(f"\n{'Frames Linked to Project':-^80}")
        cursor.execute('''
            SELECT filter, COUNT(*) as count
            FROM xisf_files
            WHERE project_id = ?
            GROUP BY filter
        ''', (project_id,))

        linked_frames = cursor.fetchall()
        if linked_frames:
            for filter_name, count in linked_frames:
                print(f"  {filter_name}: {count} frames")
        else:
            print("  No frames linked to project!")

        # Check if there are frames that SHOULD be linked
        print(f"\n{'Frames Matching Object (but not linked)':-^80}")
        cursor.execute('''
            SELECT filter, COUNT(*) as count
            FROM xisf_files
            WHERE object = ?
                AND imagetyp LIKE '%Light%'
                AND project_id IS NULL
            GROUP BY filter
        ''', (object_name,))

        unlinked_frames = cursor.fetchall()
        if unlinked_frames:
            for filter_name, count in unlinked_frames:
                print(f"  {filter_name}: {count} frames (UNLINKED)")
        else:
            print("  All matching frames are linked or no matching frames exist")

        # Show actual filter values in database
        print(f"\n{'All Unique Filters in Database':-^80}")
        cursor.execute('''
            SELECT DISTINCT filter
            FROM xisf_files
            WHERE object = ? AND imagetyp LIKE '%Light%'
            ORDER BY filter
        ''', (object_name,))

        all_filters = cursor.fetchall()
        if all_filters:
            for (filter_name,) in all_filters:
                print(f"  '{filter_name}'")
        else:
            print("  No light frames found for this object")

        # Check session assignment IDs
        print(f"\n{'Session Assignment Check':-^80}")
        cursor.execute('''
            SELECT session_assignment_id, filter, COUNT(*) as count
            FROM xisf_files
            WHERE project_id = ?
            GROUP BY session_assignment_id, filter
        ''', (project_id,))

        assignments = cursor.fetchall()
        if assignments:
            for sess_assign_id, filter_name, count in assignments:
                print(f"  Assignment {sess_assign_id}: {filter_name} - {count} frames")
        else:
            print("  No session assignments found")

    finally:
        conn.close()

def main():
    if len(sys.argv) < 3:
        print("Usage: python debug_project_counts.py <db_path> <project_id>")
        print("Example: python debug_project_counts.py xisf_catalog.db 1")
        sys.exit(1)

    db_path = sys.argv[1]
    project_id = int(sys.argv[2])

    debug_project(db_path, project_id)

if __name__ == "__main__":
    main()
