#!/usr/bin/env python3
"""
Migration script to add instrument field to calibration indexes.

This script updates existing databases to add the instrume field to
calibration indexes for improved matching performance when filtering
by instrument name.

Usage:
    python migrate_add_instrument_indexes.py [database_path]

If no database path is provided, defaults to 'xisf_catalog.db'
"""

import sqlite3
import sys
import os


def migrate_database(db_path='xisf_catalog.db'):
    """
    Add instrument field to calibration indexes.

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

        # Check if instrume column exists in xisf_files table
        cursor.execute("PRAGMA table_info(xisf_files)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'instrume' not in columns:
            print("Error: Database does not have 'instrume' column.")
            print("Please ensure the database schema is up to date.")
            conn.close()
            return False

        print("✓ Database has 'instrume' column")

        # Drop old indexes if they exist
        print("\nDropping old calibration indexes...")

        old_indexes = [
            'idx_calibration_darks',
            'idx_calibration_flats',
            'idx_calibration_bias'
        ]

        for index_name in old_indexes:
            try:
                cursor.execute(f'DROP INDEX IF EXISTS {index_name}')
                print(f"  ✓ Dropped {index_name}")
            except sqlite3.Error as e:
                print(f"  ⚠ Warning dropping {index_name}: {e}")

        # Create new indexes with instrument field
        print("\nCreating new calibration indexes with instrument field...")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_calibration_darks
            ON xisf_files(exposure, ccd_temp, xbinning, ybinning, instrume)
            WHERE imagetyp LIKE '%Dark%'
        ''')
        print("  ✓ Created idx_calibration_darks")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_calibration_flats
            ON xisf_files(filter, date_loc, ccd_temp, xbinning, ybinning, instrume)
            WHERE imagetyp LIKE '%Flat%'
        ''')
        print("  ✓ Created idx_calibration_flats")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_calibration_bias
            ON xisf_files(ccd_temp, xbinning, ybinning, instrume)
            WHERE imagetyp LIKE '%Bias%'
        ''')
        print("  ✓ Created idx_calibration_bias")

        # Create instrument index if it doesn't exist
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_instrume ON xisf_files(instrume)')
        print("  ✓ Created idx_instrume")

        # Commit changes
        conn.commit()
        conn.close()

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print("\nCalibration frame matching will now use instrument name")
        print("to ensure dark and bias frames match the camera/instrument")
        print("used for light and flat frames.")

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
