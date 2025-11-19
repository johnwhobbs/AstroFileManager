#!/usr/bin/env python3
"""
Database Version Checker for AstroFileManager

Checks if your database needs migration to v2.3.0 schema.
"""

import sqlite3
import sys
import os


def check_database(db_path):
    """Check database schema version and provide guidance."""

    if not os.path.exists(db_path):
        print(f"✗ Database not found at: {db_path}")
        print("\n📝 Action Required:")
        print("   Run: python create_db.py")
        print("   This will create a new database with the latest schema.")
        return

    print(f"Checking database: {db_path}")
    print("=" * 60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check for new tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        has_projects = 'projects' in tables
        has_filter_goals = 'project_filter_goals' in tables
        has_sessions = 'project_sessions' in tables

        # Check for new columns in xisf_files
        cursor.execute("PRAGMA table_info(xisf_files)")
        columns = [row[1] for row in cursor.fetchall()]

        has_project_id = 'project_id' in columns
        has_fwhm = 'fwhm' in columns
        has_approval = 'approval_status' in columns

        print("\n📊 Schema Check Results:")
        print(f"   Projects table: {'✓ Present' if has_projects else '✗ Missing'}")
        print(f"   Filter goals table: {'✓ Present' if has_filter_goals else '✗ Missing'}")
        print(f"   Sessions table: {'✓ Present' if has_sessions else '✗ Missing'}")
        print(f"   Quality columns: {'✓ Present' if has_fwhm else '✗ Missing'}")
        print(f"   Project columns: {'✓ Present' if has_project_id else '✗ Missing'}")

        # Determine if migration is needed
        needs_migration = not all([
            has_projects, has_filter_goals, has_sessions,
            has_project_id, has_fwhm, has_approval
        ])

        if needs_migration:
            print("\n⚠️  DATABASE NEEDS MIGRATION")
            print("\n📝 Action Required:")
            print("   Run the migration script:")
            if sys.platform == 'win32':
                print(f"   python migrations\\002_add_projects_and_quality_tracking.py {db_path}")
            else:
                print(f"   python migrations/002_add_projects_and_quality_tracking.py {db_path}")
            print("\n   This will upgrade your database to v2.3.0 schema.")
            print("   ✓ Safe to run (doesn't delete existing data)")
            print("   ✓ Can be run multiple times")
        else:
            print("\n✓ DATABASE IS UP TO DATE")
            print("   Your database has the latest v2.3.0 schema.")
            print("   No migration needed!")

        # Show record counts
        cursor.execute("SELECT COUNT(*) FROM xisf_files")
        total_files = cursor.fetchone()[0]

        if has_projects:
            cursor.execute("SELECT COUNT(*) FROM projects")
            total_projects = cursor.fetchone()[0]
            print(f"\n📈 Database Statistics:")
            print(f"   Total files: {total_files}")
            print(f"   Total projects: {total_projects}")
        else:
            print(f"\n📈 Database Statistics:")
            print(f"   Total files: {total_files}")

    except Exception as e:
        print(f"\n✗ Error checking database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'

    check_database(db_path)


if __name__ == "__main__":
    main()
