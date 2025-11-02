#!/usr/bin/env python3
"""
Read TELESCOP, INSTRUME, and OBJECT FITS header values from XISF files
"""

import xisf
import sys
import os
from pathlib import Path

def read_fits_keywords(filename, keywords=['TELESCOP', 'INSTRUME', 'OBJECT', 'FILTER','IMAGETYP','EXPOSURE','CCD-TEMP','XBINNING','YBINNING']):
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

def main():
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python script.py <xisf_file_or_folder>")
        sys.exit(1)
    
    path = sys.argv[1]
    
    # Check if path is a file or directory
    if os.path.isfile(path):
        # Single file
        files = [path]
    elif os.path.isdir(path):
        # Directory - find all .xisf files
        files = sorted(Path(path).glob('*.xisf'))
        if not files:
            print(f"No .xisf files found in directory: {path}")
            sys.exit(1)
    else:
        print(f"Error: '{path}' is not a valid file or directory")
        sys.exit(1)
    
    # Process each file
    for i, filename in enumerate(files):
        if i > 0:
            print()  # Add blank line between files
        
        print(f"File: {os.path.basename(filename)}")
        print("=" * 60)
        
        # Read the FITS keywords
        keywords = read_fits_keywords(str(filename))
        
        if keywords:
            for key, value in keywords.items():
                if value is not None:
                    print(f"{key:12s}: {value}")
                else:
                    print(f"{key:12s}: Not found")

if __name__ == "__main__":
    main()