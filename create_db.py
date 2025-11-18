#!/usr/bin/env python3
"""
Create SQLite database for XISF files with FITS keywords
"""

import sqlite3
import os
from pathlib import Path

def create_database(db_path='xisf_catalog.db'):
    """
    Create SQLite database with schema for XISF files
    
    Args:
        db_path: Path to the database file
        
    Returns:
        sqlite3.Connection object
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table with all FITS keywords and metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS xisf_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT UNIQUE NOT NULL,
            filepath TEXT NOT NULL,
            filename TEXT NOT NULL,
            telescop TEXT,
            instrume TEXT,
            object TEXT,
            filter TEXT,
            imagetyp TEXT,
            exposure REAL,
            ccd_temp REAL,
            xbinning INTEGER,
            ybinning INTEGER,
            date_loc TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for commonly queried fields
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_filename ON xisf_files(filename)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_object ON xisf_files(object)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_filter ON xisf_files(filter)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_imagetyp ON xisf_files(imagetyp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON xisf_files(file_hash)')

    # Create composite indexes for optimized View Catalog queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_catalog_hierarchy
        ON xisf_files(object, filter, date_loc, filename)
        WHERE object IS NOT NULL
    ''')

    # Create composite indexes for optimized calibration matching
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibration_darks
        ON xisf_files(exposure, ccd_temp, xbinning, ybinning)
        WHERE imagetyp LIKE '%Dark%'
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibration_flats
        ON xisf_files(filter, date_loc, ccd_temp, xbinning, ybinning)
        WHERE imagetyp LIKE '%Flat%'
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibration_bias
        ON xisf_files(ccd_temp, xbinning, ybinning)
        WHERE imagetyp LIKE '%Bias%'
    ''')
    
    conn.commit()
    
    print(f"Database created successfully: {db_path}")
    print("\nTable schema:")
    print("-" * 60)
    print("id (INTEGER PRIMARY KEY) - Unique identifier")
    print("file_hash (TEXT UNIQUE) - SHA256 hash of the file")
    print("filepath (TEXT) - Full path to the file")
    print("filename (TEXT) - Filename only")
    print("telescop (TEXT) - Telescope name")
    print("instrume (TEXT) - Instrument name")
    print("object (TEXT) - Object name")
    print("filter (TEXT) - Filter name")
    print("imagetyp (TEXT) - Image type")
    print("exposure (REAL) - Exposure time in seconds")
    print("ccd_temp (REAL) - CCD temperature")
    print("xbinning (INTEGER) - X binning")
    print("ybinning (INTEGER) - Y binning")
    print("date_loc (TEXT) - Local date/time")
    print("created_at (TIMESTAMP) - Record creation timestamp")
    print("updated_at (TIMESTAMP) - Record update timestamp")
    
    return conn

def main():
    import sys
    
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'xisf_catalog.db'
    
    # Create the database
    conn = create_database(db_path)
    conn.close()
    
    print(f"\nDatabase ready at: {os.path.abspath(db_path)}")

if __name__ == "__main__":
    main()