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
            project_id INTEGER,
            session_assignment_id INTEGER,
            fwhm REAL,
            eccentricity REAL,
            snr REAL,
            star_count INTEGER,
            background_level REAL,
            approval_status TEXT DEFAULT 'not_graded',
            grading_date TEXT,
            grading_notes TEXT,
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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_project_id ON xisf_files(project_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_assignment_id ON xisf_files(session_assignment_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_approval_status ON xisf_files(approval_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fwhm ON xisf_files(fwhm)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_instrume ON xisf_files(instrume)')

    # Create composite indexes for optimized queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_catalog_hierarchy
        ON xisf_files(object, filter, date_loc, filename)
        WHERE object IS NOT NULL
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibration_darks
        ON xisf_files(exposure, ccd_temp, xbinning, ybinning, instrume)
        WHERE imagetyp LIKE '%Dark%'
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibration_flats
        ON xisf_files(filter, date_loc, ccd_temp, xbinning, ybinning, instrume)
        WHERE imagetyp LIKE '%Flat%'
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibration_bias
        ON xisf_files(ccd_temp, xbinning, ybinning, instrume)
        WHERE imagetyp LIKE '%Bias%'
    ''')

    # Create projects table for imaging campaigns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            object_name TEXT NOT NULL,
            description TEXT,
            year INTEGER,
            start_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create project_filter_goals table for target frame counts per filter
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_filter_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            filter TEXT NOT NULL,
            target_count INTEGER NOT NULL,
            total_count INTEGER DEFAULT 0,
            approved_count INTEGER DEFAULT 0,
            last_updated TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, filter)
        )
    ''')

    # Create project_sessions table to link sessions to projects
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            date_loc TEXT NOT NULL,
            object_name TEXT,
            filter TEXT,
            frame_count INTEGER DEFAULT 0,
            approved_count INTEGER DEFAULT 0,
            rejected_count INTEGER DEFAULT 0,
            graded INTEGER DEFAULT 0,
            avg_fwhm REAL,
            notes TEXT,
            assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, session_id)
        )
    ''')

    # Create project_master_frames table to track master calibration frames for projects
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

    # Create indexes for project_master_frames
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_project_master_frames_project_id
        ON project_master_frames(project_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_project_master_frames_file_id
        ON project_master_frames(file_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_project_master_frames_type_filter
        ON project_master_frames(project_id, frame_type, filter)
    ''')

    # Performance optimizations
    # Enable WAL mode for better concurrency (allows reads during writes)
    cursor.execute('PRAGMA journal_mode=WAL')

    # Increase cache size to 64MB for better performance
    cursor.execute('PRAGMA cache_size=-64000')

    # Enable memory-mapped I/O for faster reads (256MB)
    cursor.execute('PRAGMA mmap_size=268435456')

    conn.commit()
    
    print(f"Database created successfully: {db_path}")
    print("\nTable schema:")
    print("-" * 60)
    print("xisf_files table:")
    print("  id (INTEGER PRIMARY KEY) - Unique identifier")
    print("  file_hash (TEXT UNIQUE) - SHA256 hash of the file")
    print("  filepath (TEXT) - Full path to the file")
    print("  filename (TEXT) - Filename only")
    print("  telescop (TEXT) - Telescope name")
    print("  instrume (TEXT) - Instrument name")
    print("  object (TEXT) - Object name")
    print("  filter (TEXT) - Filter name")
    print("  imagetyp (TEXT) - Image type")
    print("  exposure (REAL) - Exposure time in seconds")
    print("  ccd_temp (REAL) - CCD temperature")
    print("  xbinning (INTEGER) - X binning")
    print("  ybinning (INTEGER) - Y binning")
    print("  date_loc (TEXT) - Local date/time")
    print("  project_id (INTEGER) - Project assignment")
    print("  session_assignment_id (INTEGER) - Session assignment")
    print("  fwhm (REAL) - Full Width Half Maximum")
    print("  eccentricity (REAL) - Star eccentricity")
    print("  snr (REAL) - Signal-to-noise ratio")
    print("  star_count (INTEGER) - Number of stars")
    print("  background_level (REAL) - Background level")
    print("  approval_status (TEXT) - Grading status (not_graded/approved/rejected)")
    print("  grading_date (TEXT) - Date graded")
    print("  grading_notes (TEXT) - Grading notes")
    print("  created_at (TIMESTAMP) - Record creation timestamp")
    print("  updated_at (TIMESTAMP) - Record update timestamp")
    print("\nprojects table:")
    print("  Tracks imaging campaigns (e.g., 'M31 Narrowband 2024')")
    print("\nproject_filter_goals table:")
    print("  Tracks target frame counts per filter for each project")
    print("\nproject_sessions table:")
    print("  Links imaging sessions to projects")
    print("\nproject_master_frames table:")
    print("  Tracks master calibration frames (Master Dark/Flat/Bias) imported to projects")
    
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