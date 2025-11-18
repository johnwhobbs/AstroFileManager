"""
Background worker threads for View Catalog tab data loading.
"""

import sqlite3
from PyQt6.QtCore import QThread, pyqtSignal


class CatalogLoaderWorker(QThread):
    """Background worker thread for loading catalog data without blocking UI."""

    # Signals
    progress_updated = pyqtSignal(str)  # Status message
    data_ready = pyqtSignal(dict)  # Loaded data
    error_occurred = pyqtSignal(str)  # Error message

    def __init__(self, db_path: str, imagetype_filter: str, object_filter: str):
        """
        Initialize catalog loader worker.

        Args:
            db_path: Path to SQLite database
            imagetype_filter: Filter for image type (All, Light, Dark, etc.)
            object_filter: Filter for object name (All or specific object)
        """
        super().__init__()
        self.db_path = db_path
        self.imagetype_filter = imagetype_filter
        self.object_filter = object_filter

    def run(self):
        """Load catalog data in background thread."""
        try:
            self.progress_updated.emit("Connecting to database...")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Prepare result dictionary
            result = {
                'objects': [],  # For object filter dropdown
                'statistics': {},  # For summary stats
                'light_data': [],  # Light frames data
                'calib_data': {}  # Calibration frames data
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

            where_clause = ' AND '.join(where_conditions)

            # Load light frames if needed
            if self.imagetype_filter not in ['Dark', 'Flat', 'Bias']:
                self.progress_updated.emit("Loading light frames...")
                cursor.execute(f'''
                    SELECT
                        object, filter, date_loc, filename, imagetyp,
                        exposure, ccd_temp, xbinning, ybinning, telescop, instrume
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
