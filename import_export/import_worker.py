"""
Import worker thread for AstroFileManager.

This module contains the ImportWorker class which handles background import
of XISF files into the database.
"""

import os
import sqlite3
import hashlib
import shutil
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PyQt6.QtCore import QThread, pyqtSignal
import xisf

# Import constants from parent package
import sys
import os
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from constants import IMPORT_BATCH_SIZE, DATE_OFFSET_HOURS


def generate_organized_path(repo_path, obj, filt, imgtyp, exp, temp, xbin, ybin, date, original_filename):
    """
    Generate the organized path and filename for a file.

    Note: This function is duplicated here to avoid circular imports.
    It should match the implementation in the main module.
    """
    import re

    # Sanitize values
    obj = obj or "Unknown"
    filt = filt or "NoFilter"
    imgtyp = imgtyp or "Unknown"
    date = date or "0000-00-00"

    # Determine binning string
    if xbin and ybin:
        try:
            binning = f"Bin{int(float(xbin))}x{int(float(ybin))}"
        except (ValueError, TypeError):
            binning = "Bin1x1"
    else:
        binning = "Bin1x1"

    # Determine temp string (round to nearest degree)
    if temp is not None:
        try:
            temp_float = float(temp)
            temp_str = f"{int(round(temp_float))}C"
        except (ValueError, TypeError):
            temp_str = "0C"
    else:
        temp_str = "0C"

    # Extract sequence number from original filename if possible
    seq_match = re.search(r'_(\d+)\.(xisf|fits?)$', original_filename, re.IGNORECASE)
    seq = seq_match.group(1) if seq_match else "001"

    # Determine file type and path structure
    if 'light' in imgtyp.lower():
        # Lights/[Object]/[Filter]/[filename]
        subdir = os.path.join("Lights", obj, filt)
        try:
            exp_str = f"{int(float(exp))}s" if exp else "0s"
        except (ValueError, TypeError):
            exp_str = "0s"
        new_filename = f"{date}_{obj}_{filt}_{exp_str}_{temp_str}_{binning}_{seq}.xisf"

    elif 'dark' in imgtyp.lower():
        # Calibration/Darks/[exp]_[temp]_[binning]/[filename]
        try:
            exp_str = f"{int(float(exp))}s" if exp else "0s"
        except (ValueError, TypeError):
            exp_str = "0s"
        subdir = os.path.join("Calibration", "Darks", f"{exp_str}_{temp_str}_{binning}")
        new_filename = f"{date}_Dark_{exp_str}_{temp_str}_{binning}_{seq}.xisf"

    elif 'flat' in imgtyp.lower():
        # Calibration/Flats/[date]/[filter]_[temp]_[binning]/[filename]
        subdir = os.path.join("Calibration", "Flats", date, f"{filt}_{temp_str}_{binning}")
        new_filename = f"{date}_Flat_{filt}_{temp_str}_{binning}_{seq}.xisf"

    elif 'bias' in imgtyp.lower():
        # Calibration/Bias/[temp]_[binning]/[filename]
        subdir = os.path.join("Calibration", "Bias", f"{temp_str}_{binning}")
        new_filename = f"{date}_Bias_{temp_str}_{binning}_{seq}.xisf"

    else:
        # Unknown type - put in root with original structure
        subdir = "Uncategorized"
        new_filename = original_filename

    return os.path.join(repo_path, subdir, new_filename)


class ImportWorker(QThread):
    """Worker thread for importing XISF files"""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(int, int)  # processed, errors

    def __init__(self, files, db_path, timezone='UTC', organize=False, repo_path=None):
        super().__init__()
        self.files = files
        self.db_path = db_path
        self.timezone = timezone
        self.organize = organize
        self.repo_path = repo_path
        self.processed = 0
        self.errors = 0

    def calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        hash_obj = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def process_date_loc(self, date_str):
        """Process DATE-LOC: subtract DATE_OFFSET_HOURS and return date only in YYYY-MM-DD format"""
        if not date_str:
            return None

        try:
            # Convert to string if needed
            date_str = str(date_str).strip()

            # Handle fractional seconds that have too many digits (7+ digits instead of 6)
            # Python's %f expects exactly 6 digits for microseconds
            if 'T' in date_str and '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 2:
                    # Truncate fractional seconds to 6 digits
                    fractional = parts[1][:6]
                    date_str = f"{parts[0]}.{fractional}"

            # Try parsing common FITS date formats
            formats = [
                '%Y-%m-%dT%H:%M:%S.%f',  # With microseconds
                '%Y-%m-%dT%H:%M:%S',     # Standard ISO format
                '%Y-%m-%d %H:%M:%S',     # Space instead of T
                '%Y-%m-%d',              # Date only
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Subtract DATE_OFFSET_HOURS
                    dt = dt - timedelta(hours=DATE_OFFSET_HOURS)
                    result = dt.strftime('%Y-%m-%d')
                    return result
                except ValueError:
                    continue

            return None

        except Exception:
            return None

    def process_date_obs(self, date_str, timezone_str):
        """Process DATE-OBS: convert from UTC to local timezone, subtract DATE_OFFSET_HOURS, return date in YYYY-MM-DD format"""
        if not date_str:
            return None

        try:
            # Convert to string if needed
            date_str = str(date_str).strip()

            # Handle fractional seconds that have too many digits (7+ digits instead of 6)
            # Python's %f expects exactly 6 digits for microseconds
            if 'T' in date_str and '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 2:
                    # Truncate fractional seconds to 6 digits
                    fractional = parts[1][:6]
                    date_str = f"{parts[0]}.{fractional}"

            # Try parsing common FITS date formats
            formats = [
                '%Y-%m-%dT%H:%M:%S.%f',  # With microseconds
                '%Y-%m-%dT%H:%M:%S',     # Standard ISO format
                '%Y-%m-%d %H:%M:%S',     # Space instead of T
                '%Y-%m-%d',              # Date only
            ]

            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

            if dt is None:
                return None

            # DATE-OBS is in UTC, convert to local timezone
            try:
                # Add UTC timezone info
                dt_utc = dt.replace(tzinfo=ZoneInfo('UTC'))
                # Convert to target timezone
                target_tz = ZoneInfo(timezone_str)
                dt_local = dt_utc.astimezone(target_tz)
                # Subtract DATE_OFFSET_HOURS for session grouping
                dt_local = dt_local - timedelta(hours=DATE_OFFSET_HOURS)
                result = dt_local.strftime('%Y-%m-%d')
                return result
            except Exception:
                # If timezone conversion fails, fall back to simple subtraction
                dt = dt - timedelta(hours=DATE_OFFSET_HOURS)
                result = dt.strftime('%Y-%m-%d')
                return result

        except Exception:
            return None

    def read_fits_keywords(self, filename):
        """Read FITS keywords from XISF file"""
        keywords = ['TELESCOP', 'INSTRUME', 'OBJECT', 'FILTER', 'IMAGETYP',
                    'EXPOSURE', 'EXPTIME', 'CCD-TEMP', 'XBINNING', 'YBINNING', 'DATE-LOC', 'DATE-OBS']
        try:
            xisf_file = xisf.XISF(filename)
            im_data = xisf_file.read_image(0)

            if hasattr(xisf_file, 'fits_keywords'):
                fits_keywords = xisf_file.fits_keywords
            elif hasattr(im_data, 'fits_keywords'):
                fits_keywords = im_data.fits_keywords
            else:
                metadata = xisf_file.get_images_metadata()[0]
                fits_keywords = metadata.get('FITSKeywords', {})

            results = {}
            for keyword in keywords:
                if fits_keywords and keyword in fits_keywords:
                    keyword_data = fits_keywords[keyword]
                    if isinstance(keyword_data, list) and len(keyword_data) > 0:
                        results[keyword] = keyword_data[0]['value']
                    else:
                        results[keyword] = keyword_data
                else:
                    results[keyword] = None

            # Special handling: prefer EXPTIME over EXPOSURE (EXPTIME is FITS standard)
            # This ensures compatibility with both standard and non-standard keywords
            if results.get('EXPTIME') is not None:
                results['EXPOSURE'] = results['EXPTIME']

            return results
        except Exception as e:
            return None

    def run(self):
        """Process files and import to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Use batch processing for better performance
        batch_size = IMPORT_BATCH_SIZE
        batch_data = []

        for i, filepath in enumerate(self.files):
            basename = os.path.basename(filepath)
            self.progress.emit(i + 1, len(self.files), f"Processing: {basename}")

            try:
                # Calculate hash
                file_hash = self.calculate_file_hash(filepath)

                # Read FITS keywords
                keywords = self.read_fits_keywords(filepath)

                if keywords:
                    filename = os.path.basename(filepath)

                    # Process date: prefer DATE-LOC, fall back to DATE-OBS with timezone conversion
                    date_loc = self.process_date_loc(keywords.get('DATE-LOC'))
                    if date_loc is None and keywords.get('DATE-OBS'):
                        # DATE-LOC not available, use DATE-OBS with timezone conversion
                        date_loc = self.process_date_obs(keywords.get('DATE-OBS'), self.timezone)

                    # Determine if this is a calibration frame
                    imagetyp = keywords.get('IMAGETYP', '')
                    is_calibration = False
                    if imagetyp:
                        imagetyp_lower = imagetyp.lower()
                        is_calibration = ('dark' in imagetyp_lower or
                                        'flat' in imagetyp_lower or
                                        'bias' in imagetyp_lower)

                    # Set object to None for calibration frames (they are not object-specific)
                    obj = None if is_calibration else keywords.get('OBJECT')

                    # Organize file if requested
                    if self.organize and self.repo_path:
                        try:
                            # Generate organized path
                            organized_path = generate_organized_path(
                                self.repo_path,
                                obj,
                                keywords.get('FILTER'),
                                keywords.get('IMAGETYP'),
                                keywords.get('EXPOSURE'),
                                keywords.get('CCD-TEMP'),
                                keywords.get('XBINNING'),
                                keywords.get('YBINNING'),
                                date_loc,
                                filename
                            )

                            # Create directory if needed
                            os.makedirs(os.path.dirname(organized_path), exist_ok=True)

                            # Copy file to organized location
                            shutil.copy2(filepath, organized_path)

                            # Update filepath and filename to organized location
                            filepath = organized_path
                            filename = os.path.basename(organized_path)

                            self.progress.emit(i + 1, len(self.files), f"Organized: {filename}")
                        except Exception as e:
                            # If organization fails, keep original path and log error
                            self.progress.emit(i + 1, len(self.files), f"⚠️  Organization failed for {basename}: {str(e)} - using original path")
                            # Don't increment errors, just continue with original path

                    # Add to batch
                    batch_data.append((
                        file_hash, filepath, filename,
                        keywords.get('TELESCOP'), keywords.get('INSTRUME'),
                        obj, keywords.get('FILTER'),
                        keywords.get('IMAGETYP'), keywords.get('EXPOSURE'),
                        keywords.get('CCD-TEMP'), keywords.get('XBINNING'),
                        keywords.get('YBINNING'), date_loc
                    ))

                    # Process batch when it reaches batch_size or on last file
                    if len(batch_data) >= batch_size or i == len(self.files) - 1:
                        # Insert batch using executemany for better performance
                        cursor.execute('BEGIN TRANSACTION')

                        for data in batch_data:
                            file_hash = data[0]

                            # Check if exists
                            cursor.execute('SELECT id FROM xisf_files WHERE file_hash = ?', (file_hash,))
                            existing = cursor.fetchone()

                            if existing:
                                cursor.execute('''
                                    UPDATE xisf_files
                                    SET filepath = ?, filename = ?, telescop = ?, instrume = ?,
                                        object = ?, filter = ?, imagetyp = ?, exposure = ?,
                                        ccd_temp = ?, xbinning = ?, ybinning = ?, date_loc = ?,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE file_hash = ?
                                ''', data[1:] + (file_hash,))
                            else:
                                cursor.execute('''
                                    INSERT INTO xisf_files
                                    (file_hash, filepath, filename, telescop, instrume, object,
                                     filter, imagetyp, exposure, ccd_temp, xbinning, ybinning, date_loc)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', data)

                        conn.commit()
                        self.processed += len(batch_data)
                        batch_data = []
                else:
                    self.errors += 1

            except Exception as e:
                self.errors += 1

        conn.close()
        self.finished.emit(self.processed, self.errors)
