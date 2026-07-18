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

            # Make sure the calculated image-metric columns exist before we
            # query them. This lets older databases (created before these
            # metrics were added) load without raising "no such column" errors.
            try:
                from utils.image_metrics import ensure_metric_columns
                ensure_metric_columns(cursor)
                conn.commit()
            except Exception:
                # Non-fatal: if this fails the query below will surface a
                # clearer error to the user via error_occurred.
                pass

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

                # ``filepath`` is included last so it can be stored on each
                # file tree item. It uniquely identifies a frame (unlike
                # ``filename``, which can repeat across nights/targets), which
                # lets features such as metric calculation update the exact row.
                cursor.execute(f'''
                    SELECT
                        object, filter, date_loc, filename, imagetyp,
                        exposure, ccd_temp, xbinning, ybinning, telescop, instrume,
                        fwhm, eccentricity, snr, star_count, approval_status,
                        hfd, sky_flux_mean, star_roundness, num_stars, snr_weight,
                        filepath
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
                       telescop, instrume, ccd_temp as actual_temp, filepath
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
                       telescop, instrume, ccd_temp as actual_temp, filepath
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
                       exposure, telescop, instrume, ccd_temp as actual_temp, filter,
                       filepath
                FROM xisf_files
                WHERE {bias_where}
                ORDER BY ROUND(ccd_temp / 2.0) * 2, xbinning, ybinning, date_loc DESC, filename
            ''')
            calib_data['bias'] = cursor.fetchall()

        return calib_data


class MetricsCalculationWorker(QThread):
    """
    Background worker that calculates image quality metrics for files.

    For each requested file it computes the Half Flux Diameter, Sky Flux Mean,
    Star Roundness, number of stars and SNR Weight using Astropy and photutils,
    then stores the results in the database. Running this in a background
    thread keeps the UI responsive because the calculation can be slow for
    large images.
    """

    # Signals
    progress_updated = pyqtSignal(int, int, str)  # current, total, message
    finished_calculation = pyqtSignal(int, int)   # processed, errors
    error_occurred = pyqtSignal(str)              # fatal error message

    def __init__(self, db_path: str, filepaths: List[str]):
        """
        Initialize the metrics calculation worker.

        Args:
            db_path: Path to the SQLite database.
            filepaths: List of full file paths to process. Full paths are used
                       (instead of bare filenames) because they uniquely
                       identify a frame; filenames can repeat across different
                       nights or targets, which previously caused the metrics
                       to be written to the wrong row (or to several rows).
        """
        super().__init__()
        self.db_path = db_path
        self.filepaths = filepaths

    def run(self):
        """Calculate metrics for each file and store them in the database."""
        # Import here so the worker module does not require photutils to load.
        import os
        from utils.image_metrics import calculate_image_metrics, ensure_metric_columns

        processed = 0
        errors = 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Ensure the metric columns exist before we try to write to them.
            ensure_metric_columns(cursor)
            conn.commit()

            total = len(self.filepaths)

            for index, filepath in enumerate(self.filepaths):
                # Stop early if the user cancelled the operation.
                if self.isInterruptionRequested():
                    break

                # Show just the filename in the progress dialog for readability.
                display_name = os.path.basename(filepath) if filepath else filepath
                self.progress_updated.emit(
                    index + 1, total, f"Calculating metrics: {display_name}"
                )

                # A missing path means we cannot read the image at all.
                if not filepath:
                    errors += 1
                    continue

                try:
                    metrics = calculate_image_metrics(filepath)

                    # Update the exact row identified by its unique file path so
                    # only the selected frame's metrics are changed.
                    cursor.execute('''
                        UPDATE xisf_files
                        SET hfd = ?, sky_flux_mean = ?, star_roundness = ?,
                            num_stars = ?, snr_weight = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE filepath = ?
                    ''', (
                        metrics.get('hfd'),
                        metrics.get('sky_flux_mean'),
                        metrics.get('star_roundness'),
                        metrics.get('num_stars'),
                        metrics.get('snr_weight'),
                        filepath
                    ))
                    conn.commit()

                    # rowcount is 0 when no row matched the path (e.g. the file
                    # was removed from the database) - treat that as an error so
                    # the user is told the metrics were not stored.
                    if cursor.rowcount > 0:
                        processed += 1
                    else:
                        errors += 1
                except Exception:
                    # Skip this file but keep processing the rest.
                    errors += 1

            conn.close()
            self.finished_calculation.emit(processed, errors)

        except Exception as e:
            self.error_occurred.emit(f"Failed to calculate metrics: {str(e)}")


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
                    SUM(CASE WHEN approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
                    instrume
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
                    AND object IS NOT NULL
                GROUP BY date_loc, object, filter, instrume
                ORDER BY date_loc DESC, object, filter, instrume
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
