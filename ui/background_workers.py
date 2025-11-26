"""
Background worker threads for AstroFileManager UI tabs.

This module provides QThread workers for loading data in the background
to prevent UI freezing during database operations.
"""

import sqlite3
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, List, Any


class CatalogLoaderWorker(QThread):
    """Background worker thread for loading catalog data."""

    # Signals
    progress_updated = pyqtSignal(str)  # Status message
    data_ready = pyqtSignal(dict)  # Loaded data
    error_occurred = pyqtSignal(str)  # Error message

    def __init__(self, db_path: str, imagetype_filter: str, object_filter: str, approval_filter: str = 'All'):
        """
        Initialize catalog loader worker.

        Args:
            db_path: Path to SQLite database
            imagetype_filter: Filter for image type (All, Light, Dark, etc.)
            object_filter: Filter for object name (All or specific object)
            approval_filter: Filter for approval status (All, Approved, Rejected, Not Graded)
        """
        super().__init__()
        self.db_path = db_path
        self.imagetype_filter = imagetype_filter
        self.object_filter = object_filter
        self.approval_filter = approval_filter

    def run(self):
        """Load catalog data in background thread."""
        try:
            self.progress_updated.emit("Connecting to database...")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Prepare result dictionary
            result = {
                'objects': [],
                'light_data': [],
                'calib_data': {'darks': [], 'flats': [], 'bias': []}
            }

            # Get list of objects for dropdown
            self.progress_updated.emit("Loading object list...")
            cursor.execute('''
                SELECT DISTINCT object
                FROM xisf_files
                WHERE object IS NOT NULL
                ORDER BY object
            ''')
            result['objects'] = [row[0] for row in cursor.fetchall()]

            # Build filter conditions for light frames
            where_conditions = ['object IS NOT NULL']
            params = []

            if self.object_filter != 'All':
                where_conditions.append('object = ?')
                params.append(self.object_filter)

            if self.imagetype_filter == 'Light':
                where_conditions.append('imagetyp LIKE ?')
                params.append('%Light%')
            elif self.imagetype_filter == 'Master':
                where_conditions.append('imagetyp LIKE ?')
                params.append('%Master%')

            # Add approval status filter (only applies to light frames)
            if self.approval_filter == 'Approved':
                where_conditions.append('approval_status = ?')
                params.append('approved')
            elif self.approval_filter == 'Rejected':
                where_conditions.append('approval_status = ?')
                params.append('rejected')
            elif self.approval_filter == 'Not Graded':
                # Handle both 'not_graded' and NULL (for older records)
                where_conditions.append('(approval_status = ? OR approval_status IS NULL)')
                params.append('not_graded')

            # Load light frames if needed
            if self.imagetype_filter not in ['Dark', 'Flat', 'Bias']:
                self.progress_updated.emit("Loading light frames...")

                where_clause = ' AND '.join(where_conditions)

                cursor.execute(f'''
                    SELECT
                        object, filter, date_loc, filename, imagetyp,
                        exposure, ccd_temp, xbinning, ybinning, telescop, instrume,
                        fwhm, eccentricity, snr, star_count, approval_status
                    FROM xisf_files
                    WHERE {where_clause}
                    ORDER BY object, filter NULLS FIRST, date_loc DESC, filename
                ''', params)
                result['light_data'] = cursor.fetchall()

            # Load calibration frames if needed
            if self.imagetype_filter not in ['Light']:
                result['calib_data'] = self._load_calibration_data(cursor, self.imagetype_filter)

            conn.close()

            self.progress_updated.emit("Building tree view...")
            self.data_ready.emit(result)

        except Exception as e:
            self.error_occurred.emit(f"Failed to load catalog: {str(e)}")

    def _load_calibration_data(self, cursor, imagetype_filter):
        """Load calibration frames data."""
        calib_data = {'darks': [], 'flats': [], 'bias': []}

        # Load darks
        if imagetype_filter in ['All', 'Dark', 'Master']:
            self.progress_updated.emit("Loading dark frames...")
            dark_where = 'imagetyp LIKE "%Dark%" AND object IS NULL'
            if imagetype_filter == 'Master':
                dark_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Dark%" AND object IS NULL'

            cursor.execute(f'''
                SELECT exposure, ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                       xbinning, ybinning, date_loc, filename, imagetyp,
                       telescop, instrume, ccd_temp as actual_temp
                FROM xisf_files
                WHERE {dark_where}
                ORDER BY exposure, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, date_loc DESC, filename
            ''')
            calib_data['darks'] = cursor.fetchall()

        # Load flats
        if imagetype_filter in ['All', 'Flat', 'Master']:
            self.progress_updated.emit("Loading flat frames...")
            flat_where = 'imagetyp LIKE "%Flat%" AND object IS NULL'
            if imagetype_filter == 'Master':
                flat_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Flat%" AND object IS NULL'

            cursor.execute(f'''
                SELECT date_loc, filter, ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                       xbinning, ybinning, filename, imagetyp, exposure,
                       telescop, instrume, ccd_temp as actual_temp
                FROM xisf_files
                WHERE {flat_where}
                ORDER BY date_loc DESC, filter NULLS FIRST, ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, filename
            ''')
            calib_data['flats'] = cursor.fetchall()

        # Load bias
        if imagetype_filter in ['All', 'Bias', 'Master']:
            self.progress_updated.emit("Loading bias frames...")
            bias_where = 'imagetyp LIKE "%Bias%" AND object IS NULL'
            if imagetype_filter == 'Master':
                bias_where = 'imagetyp LIKE "%Master%" AND imagetyp LIKE "%Bias%" AND object IS NULL'

            cursor.execute(f'''
                SELECT ROUND(ccd_temp / 2.0) * 2 as ccd_temp,
                       xbinning, ybinning, date_loc, filename, imagetyp,
                       exposure, telescop, instrume, ccd_temp as actual_temp, filter
                FROM xisf_files
                WHERE {bias_where}
                ORDER BY ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, date_loc DESC, filename
            ''')
            calib_data['bias'] = cursor.fetchall()

        return calib_data


class SessionsLoaderWorker(QThread):
    """Background worker thread for loading sessions data with calibration matching."""

    # Signals
    progress_updated = pyqtSignal(str)
    data_ready = pyqtSignal(list, dict)  # (sessions_data, calib_cache)
    error_occurred = pyqtSignal(str)

    def __init__(self, db_path: str, calibration_matcher):
        """
        Initialize sessions loader worker.

        Args:
            db_path: Path to SQLite database
            calibration_matcher: CalibrationMatcher instance for matching frames
        """
        super().__init__()
        self.db_path = db_path
        self.calibration = calibration_matcher

    def run(self):
        """Load sessions data in background thread."""
        try:
            self.progress_updated.emit("Loading sessions...")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find all unique sessions
            cursor.execute('''
                SELECT
                    date_loc, object, filter,
                    COUNT(*) as frame_count,
                    AVG(exposure) as avg_exposure,
                    AVG(ccd_temp) as avg_temp,
                    xbinning, ybinning,
                    AVG(fwhm) as avg_fwhm,
                    AVG(snr) as avg_snr,
                    SUM(CASE WHEN approval_status = 'approved' THEN 1 ELSE 0 END) as approved_count,
                    SUM(CASE WHEN approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected_count
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
                    AND object IS NOT NULL
                GROUP BY date_loc, object, filter
                ORDER BY date_loc DESC, object, filter
            ''')

            sessions = cursor.fetchall()
            conn.close()

            self.progress_updated.emit("Loading calibration data...")

            # Pre-load all calibration data (OPTIMIZED - 3 queries instead of N*6)
            calib_cache = self.calibration.preload_calibration_data()

            self.progress_updated.emit("Matching calibration frames...")

            # Emit the results
            self.data_ready.emit(sessions, calib_cache)

        except Exception as e:
            self.error_occurred.emit(f"Failed to load sessions: {str(e)}")
