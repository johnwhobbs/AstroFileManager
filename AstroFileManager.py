#!/usr/bin/env python3
"""
Read FITS header values from XISF files and store in SQLite database
"""

import xisf
import sys
import os
import sqlite3
import hashlib
from pathlib import Path

def calculate_file_hash(filepath, algorithm='sha256'):
    """
    Calculate hash of a file
    
    Args:
        filepath: Path to the file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(filepath, 'rb') as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()

def read_fits_keywords(filename, keywords=['TELESCOP', 'INSTRUME', 'OBJECT', 'FILTER', 'IMAGETYP', 'EXPOSURE', 'CCD-TEMP', 'XBINNING', 'YBINNING', 'DATE-LOC']):
    """
    Read specified FITS headers from an XISF file
    
    Args:
        filename: Path to the XISF file
        keywords: List of FITS keywords to read
        
    Returns:
        Dictionary with keyword names as keys and their values
    """
    try:
        # Open the XISF file
        xisf_file = xisf.XISF(filename)
        
        # Read the file metadata
        im_data = xisf_file.read_image(0)
        
        # Access the FITS keywords from metadata
        if hasattr(xisf_file, 'fits_keywords'):
            fits_keywords = xisf_file.fits_keywords
        elif hasattr(im_data, 'fits_keywords'):
            fits_keywords = im_data.fits_keywords
        else:
            # Try accessing metadata directly
            metadata = xisf_file.get_images_metadata()[0]
            fits_keywords = metadata.get('FITSKeywords', {})
        
        # Read requested keywords
        results = {}
        for keyword in keywords:
            if fits_keywords and keyword in fits_keywords:
                keyword_data = fits_keywords[keyword]
                # FITS keywords are stored as list of dicts with 'value' and 'comment'
                if isinstance(keyword_data, list) and len(keyword_data) > 0:
                    results[keyword] = keyword_data[0]['value']
                else:
                    results[keyword] = keyword_data
            else:
                results[keyword] = None
                print(f"Warning: {keyword} keyword not found in FITS headers")
        
        return results
            
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        return None
    except Exception as e:
        print(f"Error reading XISF file: {e}")
        return None

def insert_into_database(conn, filepath, keywords, file_hash):
    """
    Insert or update XISF file information in the database
    
    Args:
        conn: SQLite connection object
        filepath: Full path to the XISF file
        keywords: Dictionary of FITS keywords
        file_hash: Hash of the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()
        
        # Check if file already exists in database
        cursor.execute('SELECT id FROM xisf_files WHERE file_hash = ?', (file_hash,))
        existing = cursor.fetchone()
        
        filename = os.path.basename(filepath)
        
        if existing:
            # Update existing record
            cursor.execute('''
                UPDATE xisf_files
                SET filepath = ?, filename = ?, telescop = ?, instrume = ?, 
                    object = ?, filter = ?, imagetyp = ?, exposure = ?,
                    ccd_temp = ?, xbinning = ?, ybinning = ?, date_loc = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_hash = ?
            ''', (
                filepath,
                filename,
                keywords.get('TELESCOP'),
                keywords.get('INSTRUME'),
                keywords.get('OBJECT'),
                keywords.get('FILTER'),
                keywords.get('IMAGETYP'),
                keywords.get('EXPOSURE'),
                keywords.get('CCD-TEMP'),
                keywords.get('XBINNING'),
                keywords.get('YBINNING'),
                keywords.get('DATE-LOC'),
                file_hash
            ))
            action = "Updated"
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO xisf_files 
                (file_hash, filepath, filename, telescop, instrume, object, 
                 filter, imagetyp, exposure, ccd_temp, xbinning, ybinning, date_loc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_hash,
                filepath,
                filename,
                keywords.get('TELESCOP'),
                keywords.get('INSTRUME'),
                keywords.get('OBJECT'),
                keywords.get('FILTER'),
                keywords.get('IMAGETYP'),
                keywords.get('EXPOSURE'),
                keywords.get('CCD-TEMP'),
                keywords.get('XBINNING'),
                keywords.get('YBINNING'),
                keywords.get('DATE-LOC')
            ))
            action = "Inserted"
        
        conn.commit()
        return action
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python script.py <xisf_file_or_folder> [database_path]")
        print("  xisf_file_or_folder: Path to XISF file or folder containing XISF files")
        print("  database_path: Optional path to SQLite database (default: xisf_catalog.db)")
        sys.exit(1)
    
    path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else 'xisf_catalog.db'
    
    # Connect to database
    if not os.path.exists(db_path):
        print(f"Error: Database '{db_path}' does not exist.")
        print("Please create it first using the database creation script.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    print(f"Connected to database: {db_path}\n")
    
    # Check if path is a file or directory
    if os.path.isfile(path):
        # Single file
        files = [path]
    elif os.path.isdir(path):
        # Directory - find all .xisf files
        files = sorted(Path(path).glob('*.xisf'))
        if not files:
            print(f"No .xisf files found in directory: {path}")
            conn.close()
            sys.exit(1)
    else:
        print(f"Error: '{path}' is not a valid file or directory")
        conn.close()
        sys.exit(1)
    
    # Process each file
    processed = 0
    errors = 0
    
    for i, filename in enumerate(files):
        filepath = str(filename)
        basename = os.path.basename(filepath)
        
        print(f"[{i+1}/{len(files)}] Processing: {basename}")
        
        try:
            # Calculate file hash
            print(f"  Calculating hash...")
            file_hash = calculate_file_hash(filepath)
            
            # Read FITS keywords
            print(f"  Reading FITS keywords...")
            keywords = read_fits_keywords(filepath)
            
            if keywords:
                # Insert into database
                action = insert_into_database(conn, filepath, keywords, file_hash)
                
                if action:
                    print(f"  {action} in database")
                    processed += 1
                    
                    # Display key information
                    obj = keywords.get('OBJECT', 'N/A')
                    filt = keywords.get('FILTER', 'N/A')
                    exp = keywords.get('EXPOSURE', 'N/A')
                    print(f"  Object: {obj}, Filter: {filt}, Exposure: {exp}s")
                else:
                    print(f"  Failed to insert into database")
                    errors += 1
            else:
                print(f"  Failed to read FITS keywords")
                errors += 1
                
        except Exception as e:
            print(f"  Error processing file: {e}")
            errors += 1
        
        print()
    
    conn.close()
    
    # Summary
    print("=" * 60)
    print(f"Processing complete!")
    print(f"Successfully processed: {processed}")
    print(f"Errors: {errors}")
    print(f"Total files: {len(files)}")


if __name__ == "__main__":
    main()