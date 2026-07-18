#!/usr/bin/env python3
"""
Migration script to add calculated image-metric columns to the database.

This adds the columns used to store metrics that AstroFileManager now
calculates itself (using Astropy and photutils) instead of importing them
from PixInsight's SubFrame Selector:

    * hfd            - Half Flux Diameter
    * sky_flux_mean  - Sky (background) flux mean
    * star_roundness - Average star roundness
    * num_stars      - Number of detected stars
    * snr_weight     - Relative signal-to-noise weight

The migration is idempotent: running it multiple times is safe because it
only adds columns that do not already exist.

Usage:
    python migrate_add_image_metrics.py [database_path]

If no database path is provided, defaults to 'xisf_catalog.db'.
"""

import sqlite3
import sys
import os

# Make sure we can import the shared column definitions from utils.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.image_metrics import METRIC_COLUMNS, ensure_metric_columns


def migrate_database(db_path='xisf_catalog.db'):
    """
    Add the calculated image-metric columns to the xisf_files table.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if migration succeeded, False otherwise.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        return False

    print(f"Migrating database: {db_path}")
    print("-" * 60)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Record which metric columns already exist so we can report clearly.
        cursor.execute("PRAGMA table_info(xisf_files)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Perform the idempotent migration.
        ensure_metric_columns(cursor)

        conn.commit()
        conn.close()

        # Report what happened for each metric column.
        for column_name in METRIC_COLUMNS:
            if column_name in existing_columns:
                print(f"  • {column_name}: already present (skipped)")
            else:
                print(f"  ✓ {column_name}: added")

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        return True

    except sqlite3.Error as e:
        print(f"\nError during migration: {e}")
        return False


def main():
    """Main entry point for the migration script."""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'

    success = migrate_database(db_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
