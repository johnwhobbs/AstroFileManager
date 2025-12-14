"""
Background worker for exporting project files with calibration frames.

Handles copying light frames and matching calibration frames to a destination
folder for processing with PixInsight WBPP or other tools.
"""

import os
import shutil
import sqlite3
from pathlib import Path
from typing import List, Dict, Set, Tuple
from PyQt6.QtCore import QThread, pyqtSignal

from core.calibration import CalibrationMatcher
from core.database import DatabaseManager


class ExportProjectWorker(QThread):
    """Background worker for exporting project files."""

    # Signals
    progress_updated = pyqtSignal(int, str)  # (progress_percent, status_message)
    finished_successfully = pyqtSignal(int, int, int, int)  # (light_count, dark_count, flat_count, bias_count)
    error_occurred = pyqtSignal(str)

    def __init__(self, db_path: str, project_id: int, destination_path: str,
                 calibration_matcher: CalibrationMatcher):
        """
        Initialize export worker.

        Args:
            db_path: Path to database
            project_id: Project ID to export
            destination_path: Destination folder path
            calibration_matcher: CalibrationMatcher instance for finding calibration frames
        """
        super().__init__()
        self.db_path = db_path
        self.project_id = project_id
        self.destination_path = destination_path
        self.calibration_matcher = calibration_matcher
        self.db_manager = DatabaseManager(db_path)

    def run(self):
        """Run the export process."""
        try:
            # Create destination subdirectories
            lights_dir = Path(self.destination_path) / "Lights"
            darks_dir = Path(self.destination_path) / "Darks"
            flats_dir = Path(self.destination_path) / "Flats"
            bias_dir = Path(self.destination_path) / "Bias"

            lights_dir.mkdir(parents=True, exist_ok=True)
            darks_dir.mkdir(parents=True, exist_ok=True)
            flats_dir.mkdir(parents=True, exist_ok=True)
            bias_dir.mkdir(parents=True, exist_ok=True)

            self.progress_updated.emit(0, "Gathering light frames...")

            # Get all light frames for the project
            light_frames = self._get_project_light_frames()
            if not light_frames:
                self.error_occurred.emit("No light frames found for this project")
                return

            self.progress_updated.emit(5, f"Found {len(light_frames)} light frames")

            # Find all unique calibration requirements
            self.progress_updated.emit(10, "Analyzing calibration requirements...")
            calib_files = self._find_required_calibration_frames(light_frames)

            # Calculate total files to copy
            total_files = (len(light_frames) +
                          len(calib_files['darks']) +
                          len(calib_files['flats']) +
                          len(calib_files['bias']))

            if total_files == 0:
                self.error_occurred.emit("No files to checkout")
                return

            copied_count = 0

            # Copy light frames
            self.progress_updated.emit(15, "Copying light frames...")
            for filepath in light_frames:
                if self._copy_file(filepath, lights_dir):
                    copied_count += 1
                progress = 15 + int((copied_count / total_files) * 70)
                self.progress_updated.emit(progress, f"Copying files ({copied_count}/{total_files})...")

            # Copy dark frames
            self.progress_updated.emit(60, "Copying dark frames...")
            for filepath in calib_files['darks']:
                if self._copy_file(filepath, darks_dir):
                    copied_count += 1
                progress = 15 + int((copied_count / total_files) * 70)
                self.progress_updated.emit(progress, f"Copying files ({copied_count}/{total_files})...")

            # Copy flat frames
            self.progress_updated.emit(75, "Copying flat frames...")
            for filepath in calib_files['flats']:
                if self._copy_file(filepath, flats_dir):
                    copied_count += 1
                progress = 15 + int((copied_count / total_files) * 70)
                self.progress_updated.emit(progress, f"Copying files ({copied_count}/{total_files})...")

            # Copy bias frames
            self.progress_updated.emit(90, "Copying bias frames...")
            for filepath in calib_files['bias']:
                if self._copy_file(filepath, bias_dir):
                    copied_count += 1
                progress = 15 + int((copied_count / total_files) * 70)
                self.progress_updated.emit(progress, f"Copying files ({copied_count}/{total_files})...")

            self.progress_updated.emit(100, "Checkout complete!")
            self.finished_successfully.emit(
                len(light_frames),
                len(calib_files['darks']),
                len(calib_files['flats']),
                len(calib_files['bias'])
            )

        except Exception as e:
            self.error_occurred.emit(f"Checkout failed: {str(e)}")

    def _get_project_light_frames(self) -> List[str]:
        """Get all light frame file paths for the project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT DISTINCT filepath
                FROM xisf_files
                WHERE project_id = ?
                AND imagetyp LIKE '%Light%'
                AND filepath IS NOT NULL
                ORDER BY date_loc, filter, filepath
            ''', (self.project_id,))

            return [row[0] for row in cursor.fetchall()]

        finally:
            conn.close()

    def _find_required_calibration_frames(self, light_frames: List[str]) -> Dict[str, Set[str]]:
        """
        Find all unique calibration frames needed for the light frames.

        Args:
            light_frames: List of light frame file paths

        Returns:
            Dictionary with sets of file paths for darks, flats, bias
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        darks_set = set()
        flats_set = set()
        bias_set = set()

        try:
            # For each light frame, find its calibration requirements
            for filepath in light_frames:
                # Get light frame metadata
                cursor.execute('''
                    SELECT exposure, ccd_temp, xbinning, ybinning, filter, date_loc
                    FROM xisf_files
                    WHERE filepath = ?
                ''', (filepath,))

                result = cursor.fetchone()
                if not result:
                    continue

                exposure, temp, xbin, ybin, filt, date_loc = result

                # Find matching darks for light frames
                darks = self._find_dark_files(cursor, exposure, temp, xbin, ybin)
                darks_set.update(darks)

                # Find matching flats
                flats = self._find_flat_files(cursor, filt, temp, xbin, ybin, date_loc)
                flats_set.update(flats)

                # Find matching bias
                bias = self._find_bias_files(cursor, temp, xbin, ybin)
                bias_set.update(bias)

            # Find darks for the flat frames
            # Flats need their own darks that match the flat exposure times
            for flat_filepath in flats_set:
                # Get flat frame metadata to find matching darks
                cursor.execute('''
                    SELECT exposure, ccd_temp, xbinning, ybinning
                    FROM xisf_files
                    WHERE filepath = ?
                ''', (flat_filepath,))

                result = cursor.fetchone()
                if not result:
                    continue

                flat_exposure, flat_temp, flat_xbin, flat_ybin = result

                # Find darks that match the flat frame parameters
                flat_darks = self._find_dark_files(cursor, flat_exposure, flat_temp, flat_xbin, flat_ybin)
                darks_set.update(flat_darks)

            return {
                'darks': darks_set,
                'flats': flats_set,
                'bias': bias_set
            }

        finally:
            conn.close()

    def _find_dark_files(self, cursor, exposure: float, temp: float,
                        xbin: int, ybin: int) -> Set[str]:
        """Find matching dark frame file paths."""
        temp_tolerance = self.calibration_matcher.temp_tolerance_darks
        exp_tolerance = self.calibration_matcher.exposure_tolerance

        temp_min = temp - temp_tolerance if temp else -999
        temp_max = temp + temp_tolerance if temp else 999

        cursor.execute(f'''
            SELECT DISTINCT filepath
            FROM xisf_files
            WHERE imagetyp LIKE '%Dark%'
                AND ABS(exposure - ?) < {exp_tolerance}
                AND ccd_temp BETWEEN ? AND ?
                AND xbinning = ?
                AND ybinning = ?
                AND filepath IS NOT NULL
        ''', (exposure, temp_min, temp_max, xbin, ybin))

        return {row[0] for row in cursor.fetchall()}

    def _find_flat_files(self, cursor, filt: str, temp: float,
                        xbin: int, ybin: int, date_loc: str) -> Set[str]:
        """Find matching flat frame file paths."""
        temp_tolerance = self.calibration_matcher.temp_tolerance_flats

        temp_min = temp - temp_tolerance if temp else -999
        temp_max = temp + temp_tolerance if temp else 999

        # Try to find flats from same date first
        cursor.execute('''
            SELECT DISTINCT filepath
            FROM xisf_files
            WHERE imagetyp LIKE '%Flat%'
                AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                AND ccd_temp BETWEEN ? AND ?
                AND xbinning = ?
                AND ybinning = ?
                AND date_loc = ?
                AND filepath IS NOT NULL
        ''', (filt, filt, temp_min, temp_max, xbin, ybin, date_loc))

        flats = {row[0] for row in cursor.fetchall()}

        # If no flats from same date, look for any matching flats
        if not flats:
            cursor.execute('''
                SELECT DISTINCT filepath
                FROM xisf_files
                WHERE imagetyp LIKE '%Flat%'
                    AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                    AND ccd_temp BETWEEN ? AND ?
                    AND xbinning = ?
                    AND ybinning = ?
                    AND filepath IS NOT NULL
                ORDER BY date_loc DESC
                LIMIT 50
            ''', (filt, filt, temp_min, temp_max, xbin, ybin))

            flats = {row[0] for row in cursor.fetchall()}

        return flats

    def _find_bias_files(self, cursor, temp: float, xbin: int, ybin: int) -> Set[str]:
        """Find matching bias frame file paths."""
        temp_tolerance = self.calibration_matcher.temp_tolerance_bias

        temp_min = temp - temp_tolerance if temp else -999
        temp_max = temp + temp_tolerance if temp else 999

        cursor.execute('''
            SELECT DISTINCT filepath
            FROM xisf_files
            WHERE imagetyp LIKE '%Bias%'
                AND ccd_temp BETWEEN ? AND ?
                AND xbinning = ?
                AND ybinning = ?
                AND filepath IS NOT NULL
        ''', (temp_min, temp_max, xbin, ybin))

        return {row[0] for row in cursor.fetchall()}

    def _copy_file(self, source_path: str, dest_dir: Path) -> bool:
        """
        Copy a file to the destination directory.

        Args:
            source_path: Source file path
            dest_dir: Destination directory

        Returns:
            True if successful, False otherwise
        """
        try:
            source = Path(source_path)
            if not source.exists():
                return False

            dest = dest_dir / source.name

            # If file already exists with same name, don't overwrite
            if dest.exists():
                return True

            shutil.copy2(source, dest)
            return True

        except Exception as e:
            # Log error but continue with other files
            print(f"Error copying {source_path}: {e}")
            return False
