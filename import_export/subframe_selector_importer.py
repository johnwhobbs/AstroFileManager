"""
SubFrame Selector CSV Importer for AstroFileManager

Imports quality metrics from PixInsight SubFrame Selector CSV files.
"""

import csv
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class SubFrameSelectorImporter:
    """Imports quality metrics from PixInsight SubFrame Selector CSV files."""

    def __init__(self, db_path: str):
        """
        Initialize SubFrame Selector importer.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def import_csv(
        self,
        csv_path: str,
        approval_column: str = "Approved",
        match_by_filename: bool = True
    ) -> Dict[str, any]:
        """
        Import quality metrics from PixInsight SubFrame Selector CSV.

        Args:
            csv_path: Path to CSV file
            approval_column: Column name for approval status ("Approved", "Weight", etc.)
            match_by_filename: If True, match by filename only; if False, match by full path

        Returns:
            Dictionary with import statistics

        Raises:
            FileNotFoundError: If CSV file not found
            ValueError: If CSV format is invalid
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Read CSV and extract data
        frames_data = self._parse_csv(csv_path, approval_column)

        if not frames_data:
            raise ValueError("No valid data found in CSV file")

        # Import into database
        stats = self._import_frames_data(frames_data, match_by_filename)

        return stats

    def _parse_csv(
        self,
        csv_path: str,
        approval_column: str
    ) -> List[Dict]:
        """
        Parse PixInsight SubFrame Selector CSV file.

        Args:
            csv_path: Path to CSV file
            approval_column: Column name for approval status

        Returns:
            List of dictionaries containing frame data

        Raises:
            ValueError: If CSV format is invalid
        """
        frames_data = []

        with open(csv_path, 'r', encoding='utf-8') as f:
            # Skip metadata header lines until we find "Index,"
            header_line = None
            for line_num, line in enumerate(f, 1):
                if line.startswith('Index,'):
                    header_line = line.strip()
                    break

            if not header_line:
                raise ValueError(
                    "Invalid CSV format: Could not find 'Index,' header line"
                )

            # Parse header
            headers = [h.strip() for h in header_line.split(',')]

            # Verify required columns
            required_columns = ['Index', 'File']
            for col in required_columns:
                if col not in headers:
                    raise ValueError(f"CSV missing required column: {col}")

            # Map column names to indices
            col_map = {h: i for i, h in enumerate(headers)}

            # Read data rows
            reader = csv.reader(f)
            for row_num, row in enumerate(reader, line_num + 1):
                if not row or not row[0].strip():
                    continue  # Skip empty rows

                try:
                    frame_data = self._extract_frame_data(row, col_map, approval_column)
                    if frame_data:
                        frames_data.append(frame_data)
                except Exception as e:
                    # Log warning but continue processing
                    print(f"Warning: Skipping row {row_num}: {e}")

        return frames_data

    def _extract_frame_data(
        self,
        row: List[str],
        col_map: Dict[str, int],
        approval_column: str
    ) -> Optional[Dict]:
        """
        Extract frame data from a CSV row.

        Args:
            row: CSV row data
            col_map: Column name to index mapping
            approval_column: Column name for approval status

        Returns:
            Dictionary with frame data or None if invalid
        """
        def get_value(col_name: str, default=None):
            """Get value from row by column name."""
            if col_name not in col_map:
                return default
            idx = col_map[col_name]
            if idx >= len(row):
                return default
            value = row[idx].strip()
            return value if value else default

        # Get filename
        filename = get_value('File')
        if not filename:
            return None

        # Extract just the filename (not full path)
        filename = os.path.basename(filename)

        # Determine approval status
        approval_status = 'not_graded'

        if approval_column in col_map:
            approval_value = get_value(approval_column)
            if approval_value:
                approval_lower = approval_value.lower()

                # First check if it's a boolean text value (True/False, Yes/No)
                if approval_lower in ['true', '1', 'yes', 'approved']:
                    approval_status = 'approved'
                elif approval_lower in ['false', '0', 'no', 'rejected']:
                    approval_status = 'rejected'
                # Then try numeric weight (for Weight column)
                else:
                    try:
                        weight = float(approval_value)
                        approval_status = 'approved' if weight > 0 else 'rejected'
                    except ValueError:
                        # Not a boolean text and not a number, mark as not graded
                        approval_status = 'not_graded'

        # Extract quality metrics
        frame_data = {
            'filename': filename,
            'approval_status': approval_status,
            'fwhm': self._parse_float(get_value('FWHM')),
            'eccentricity': self._parse_float(get_value('Eccentricity')),
            'snr': self._parse_float(get_value('SNR') or get_value('SNRWeight')),
            'star_count': self._parse_int(get_value('Stars')),
            'background_level': self._parse_float(get_value('Median')),
            'grading_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return frame_data

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float value safely."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse int value safely."""
        if value is None:
            return None
        try:
            return int(float(value))  # Handle "123.0" format
        except (ValueError, TypeError):
            return None

    def _import_frames_data(
        self,
        frames_data: List[Dict],
        match_by_filename: bool
    ) -> Dict[str, any]:
        """
        Import frames data into database.

        Args:
            frames_data: List of frame data dictionaries
            match_by_filename: If True, match by filename only

        Returns:
            Dictionary with import statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {
            'total_csv_frames': len(frames_data),
            'matched': 0,
            'not_found': 0,
            'approved': 0,
            'rejected': 0,
            'not_graded': 0,
            'updated_projects': set()
        }

        try:
            for frame in frames_data:
                filename = frame['filename']

                # Find matching frame in database
                if match_by_filename:
                    cursor.execute(
                        'SELECT id, project_id FROM xisf_files WHERE filename = ?',
                        (filename,)
                    )
                else:
                    cursor.execute(
                        'SELECT id, project_id FROM xisf_files WHERE filepath LIKE ?',
                        (f'%{filename}',)
                    )

                result = cursor.fetchone()

                if not result:
                    stats['not_found'] += 1
                    continue

                file_id, project_id = result
                stats['matched'] += 1

                # Update quality metrics
                cursor.execute('''
                    UPDATE xisf_files
                    SET fwhm = ?,
                        eccentricity = ?,
                        snr = ?,
                        star_count = ?,
                        background_level = ?,
                        approval_status = ?,
                        grading_date = ?
                    WHERE id = ?
                ''', (
                    frame['fwhm'],
                    frame['eccentricity'],
                    frame['snr'],
                    frame['star_count'],
                    frame['background_level'],
                    frame['approval_status'],
                    frame['grading_date'],
                    file_id
                ))

                # Track approval counts
                stats[frame['approval_status']] += 1

                # Track projects that need updating
                if project_id:
                    stats['updated_projects'].add(project_id)

            # Update project_sessions grading status
            for project_id in stats['updated_projects']:
                self._update_project_grading_status(cursor, project_id)

            # Update project filter goal counts
            for project_id in stats['updated_projects']:
                self._update_project_filter_goals(cursor, project_id)

            conn.commit()

            # Convert set to count for return
            stats['updated_projects'] = len(stats['updated_projects'])

        except Exception as e:
            conn.rollback()
            raise

        finally:
            conn.close()

        return stats

    def _update_project_grading_status(self, cursor, project_id: int):
        """
        Update project_sessions grading status.

        Args:
            cursor: SQLite cursor
            project_id: Project ID
        """
        # Update graded flag and counts for each session
        cursor.execute('''
            UPDATE project_sessions
            SET
                graded = CASE
                    WHEN (
                        SELECT COUNT(*)
                        FROM xisf_files
                        WHERE session_assignment_id = project_sessions.id
                        AND approval_status = 'not_graded'
                    ) = 0 THEN 1
                    ELSE 0
                END,
                approved_count = (
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE session_assignment_id = project_sessions.id
                    AND approval_status = 'approved'
                ),
                rejected_count = (
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE session_assignment_id = project_sessions.id
                    AND approval_status = 'rejected'
                ),
                avg_fwhm = (
                    SELECT AVG(fwhm)
                    FROM xisf_files
                    WHERE session_assignment_id = project_sessions.id
                    AND fwhm IS NOT NULL
                )
            WHERE project_id = ?
        ''', (project_id,))

    def _update_project_filter_goals(self, cursor, project_id: int):
        """
        Update project filter goal counts.

        Args:
            cursor: SQLite cursor
            project_id: Project ID
        """
        cursor.execute('''
            UPDATE project_filter_goals
            SET
                total_count = (
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE project_id = ? AND filter = project_filter_goals.filter
                ),
                approved_count = (
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE project_id = ? AND filter = project_filter_goals.filter
                    AND approval_status = 'approved'
                ),
                last_updated = CURRENT_TIMESTAMP
            WHERE project_id = ?
        ''', (project_id, project_id, project_id))
