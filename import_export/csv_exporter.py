"""
CSV export functionality for AstroFileManager.

This module contains the CSVExporter class which handles exporting
XISF file catalog data to CSV format.
"""

import csv
import sqlite3
from typing import Optional


class CSVExporter:
    """Handles CSV export operations for XISF file catalog."""

    @staticmethod
    def export_tree_group(filepath: str, tree_item) -> None:
        """
        Export a tree group (and its children) to CSV.

        Args:
            filepath: Path to save CSV file
            tree_item: QTreeWidgetItem to export

        Raises:
            Exception: If export fails
        """
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Filename', 'Image Type', 'Filter', 'Exposure', 'Temp',
                'Binning', 'Date', 'Telescope', 'Instrument'
            ])

            def write_items(item):
                # Only write file items (leaf nodes)
                if item.childCount() == 0 and '(' not in item.text(0):
                    row = [item.text(i) for i in range(9)]
                    writer.writerow(row)
                # Recurse to children
                for i in range(item.childCount()):
                    write_items(item.child(i))

            write_items(tree_item)

    @staticmethod
    def export_catalog(filepath: str, db_path: str) -> int:
        """
        Export entire catalog to CSV.

        Args:
            filepath: Path to save CSV file
            db_path: Path to SQLite database

        Returns:
            Number of rows exported

        Raises:
            Exception: If export fails
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT filename, imagetyp, filter, exposure, ccd_temp,
                   xbinning, ybinning, date_loc, telescop, instrume, filepath, object
            FROM xisf_files
            ORDER BY object, filter, date_loc, filename
        ''')
        rows = cursor.fetchall()
        conn.close()

        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Filename', 'Image Type', 'Filter', 'Exposure', 'Temp',
                'Binning', 'Date', 'Telescope', 'Instrument', 'Filepath', 'Object'
            ])

            for row in rows:
                # Format the row
                formatted_row = [
                    row[0],  # filename
                    row[1] or 'N/A',  # imagetyp
                    row[2] or 'N/A',  # filter
                    f"{row[3]:.1f}s" if row[3] else 'N/A',  # exposure
                    f"{row[4]:.1f}°C" if row[4] is not None else 'N/A',  # temp
                    f"{int(row[5])}x{int(row[6])}" if row[5] and row[6] else 'N/A',  # binning
                    row[7] or 'N/A',  # date
                    row[8] or 'N/A',  # telescope
                    row[9] or 'N/A',  # instrument
                    row[10] or 'N/A',  # filepath
                    row[11] or 'N/A',  # object
                ]
                writer.writerow(formatted_row)

        return len(rows)
