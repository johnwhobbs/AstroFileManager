"""
Database operations for AstroFileManager.

This module centralizes all database operations, providing a clean interface
for CRUD operations and queries.
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Tuple, Any


class DatabaseManager:
    """Centralized database operations manager."""

    def __init__(self, db_path: str):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections with performance optimizations.

        Yields:
            sqlite3.Connection: Database connection

        Example:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        conn = sqlite3.connect(self.db_path)

        # Apply performance optimizations
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging
        cursor.execute('PRAGMA cache_size=-64000')  # 64MB cache
        cursor.execute('PRAGMA mmap_size=268435456')  # 256MB memory-mapped I/O
        cursor.execute('PRAGMA synchronous=NORMAL')  # Faster writes, still safe with WAL

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_catalog_statistics(self) -> Dict[str, Any]:
        """
        Get catalog summary statistics.

        Returns:
            Dictionary with total_files, total_exposure, unique_objects,
            frame_counts (light, dark, flat, bias), date_range
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total files
            cursor.execute('SELECT COUNT(*) FROM xisf_files')
            total_files = cursor.fetchone()[0]

            # Total exposure for light frames (in hours)
            cursor.execute('''
                SELECT SUM(exposure) / 3600.0
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
            ''')
            total_exposure = cursor.fetchone()[0] or 0.0

            # Unique objects
            cursor.execute('''
                SELECT COUNT(DISTINCT object)
                FROM xisf_files
                WHERE object IS NOT NULL
            ''')
            unique_objects = cursor.fetchone()[0]

            # Frame type breakdown
            frame_counts = {}
            for frame_type in ['Light', 'Dark', 'Flat', 'Bias']:
                cursor.execute(f'''
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE imagetyp LIKE '%{frame_type}%'
                ''')
                frame_counts[frame_type.lower()] = cursor.fetchone()[0]

            # Date range
            cursor.execute('''
                SELECT MIN(date_loc), MAX(date_loc)
                FROM xisf_files
                WHERE date_loc IS NOT NULL
            ''')
            min_date, max_date = cursor.fetchone()
            date_range = f"{min_date} to {max_date}" if min_date and max_date else "N/A"

            return {
                'total_files': total_files,
                'total_exposure': total_exposure,
                'unique_objects': unique_objects,
                'frame_counts': frame_counts,
                'date_range': date_range,
                'min_date': min_date,
                'max_date': max_date
            }

    def get_files_grouped_by_hierarchy(self, imagetype_filter: str = 'All',
                                      object_filter: str = 'All') -> List[Dict]:
        """
        Get files organized in hierarchical structure for catalog view.

        Args:
            imagetype_filter: Filter by image type (All, Light, Dark, Flat, Bias, Master)
            object_filter: Filter by object name

        Returns:
            List of file records with hierarchical grouping information
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # This will be used by the UI to build the tree
            # For now, return all files that match filters
            where_conditions = []
            params = []

            if imagetype_filter != 'All':
                where_conditions.append('imagetyp LIKE ?')
                params.append(f'%{imagetype_filter}%')

            if object_filter != 'All':
                where_conditions.append('object = ?')
                params.append(object_filter)

            where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'

            cursor.execute(f'''
                SELECT filename, imagetyp, filter, exposure, ccd_temp,
                       xbinning, ybinning, date_loc, telescop, instrume,
                       filepath, object
                FROM xisf_files
                WHERE {where_clause}
                ORDER BY date_loc DESC, object, imagetyp
            ''', params)

            columns = ['filename', 'imagetyp', 'filter', 'exposure', 'ccd_temp',
                      'xbinning', 'ybinning', 'date_loc', 'telescop', 'instrume',
                      'filepath', 'object']

            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_distinct_objects(self) -> List[str]:
        """
        Get list of distinct object names.

        Returns:
            List of object names, sorted alphabetically
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT object
                FROM xisf_files
                WHERE object IS NOT NULL
                ORDER BY object
            ''')
            return [row[0] for row in cursor.fetchall()]

    def get_file_by_filename(self, filename: str) -> Optional[Dict]:
        """
        Get file details by filename.

        Args:
            filename: Name of the file

        Returns:
            Dictionary with file details or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT filepath, telescop, instrume, object, filter, imagetyp,
                       exposure, ccd_temp, xbinning, ybinning, date_loc, created_at
                FROM xisf_files
                WHERE filename = ?
            ''', (filename,))
            result = cursor.fetchone()

            if result:
                columns = ['filepath', 'telescop', 'instrume', 'object', 'filter',
                          'imagetyp', 'exposure', 'ccd_temp', 'xbinning', 'ybinning',
                          'date_loc', 'created_at']
                return dict(zip(columns, result))
            return None

    def get_filepath_by_filename(self, filename: str) -> Optional[str]:
        """
        Get filepath for a given filename.

        Args:
            filename: Name of the file

        Returns:
            Full filepath or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filepath FROM xisf_files WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            return result[0] if result else None

    def insert_files_batch(self, file_data: List[Tuple]) -> None:
        """
        Insert multiple files in a batch.

        Args:
            file_data: List of tuples containing file data in the correct order
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR REPLACE INTO xisf_files
                (filename, filepath, file_hash, telescop, instrume, object, filter,
                 imagetyp, exposure, ccd_temp, xbinning, ybinning, date_loc, date_obs,
                 timezone, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', file_data)

    def delete_file_by_filename(self, filename: str) -> None:
        """
        Delete a file from the database by filename.

        Args:
            filename: Name of the file to delete
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM xisf_files WHERE filename = ?', (filename,))

    def clear_all_files(self) -> None:
        """Delete all files from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM xisf_files')

    def get_current_keyword_values(self, keyword: str) -> List[str]:
        """
        Get distinct current values for a keyword/column.

        Args:
            keyword: Column name to get values for

        Returns:
            List of distinct values
        """
        # Map FITS keywords to database column names
        column_map = {
            'TELESCOP': 'telescop',
            'INSTRUME': 'instrume',
            'OBJECT': 'object',
            'FILTER': 'filter',
            'IMAGETYP': 'imagetyp'
        }

        column = column_map.get(keyword, keyword.lower())

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT DISTINCT {column}
                FROM xisf_files
                WHERE {column} IS NOT NULL
                ORDER BY {column}
            ''')
            return [row[0] for row in cursor.fetchall()]

    def replace_keyword_values(self, keyword: str, old_value: str,
                               new_value: str) -> int:
        """
        Replace values for a specific keyword across all files.

        Args:
            keyword: FITS keyword to update
            old_value: Value to replace
            new_value: New value

        Returns:
            Number of rows updated
        """
        # Map FITS keywords to database column names
        column_map = {
            'TELESCOP': 'telescop',
            'INSTRUME': 'instrume',
            'OBJECT': 'object',
            'FILTER': 'filter',
            'IMAGETYP': 'imagetyp'
        }

        column = column_map.get(keyword, keyword.lower())

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE xisf_files
                SET {column} = ?
                WHERE {column} = ?
            ''', (new_value, old_value))
            return cursor.rowcount

    def get_files_for_organization(self) -> List[Tuple]:
        """
        Get all files with metadata needed for organization.

        Returns:
            List of tuples: (filepath, filename, object, filter, imagetyp,
                            exposure, ccd_temp, xbinning, ybinning, date_loc)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT filepath, filename, object, filter, imagetyp,
                       exposure, ccd_temp, xbinning, ybinning, date_loc
                FROM xisf_files
                ORDER BY date_loc, object, imagetyp
            ''')
            return cursor.fetchall()

    def get_files_for_organization_with_id(self) -> List[Tuple]:
        """
        Get all files with ID for organization execution.

        Returns:
            List of tuples: (id, filepath, filename, object, filter, imagetyp,
                            exposure, ccd_temp, xbinning, ybinning, date_loc)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, filepath, filename, object, filter, imagetyp,
                       exposure, ccd_temp, xbinning, ybinning, date_loc
                FROM xisf_files
                ORDER BY date_loc, object, imagetyp
            ''')
            return cursor.fetchall()

    def update_file_path(self, file_id: int, new_path: str) -> None:
        """
        Update filepath for a file.

        Args:
            file_id: Database ID of the file
            new_path: New filepath
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE xisf_files
                SET filepath = ?
                WHERE id = ?
            ''', (new_path, file_id))

    def get_analytics_years(self) -> List[str]:
        """
        Get distinct years that have data.

        Returns:
            List of years as strings, sorted descending
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT strftime("%Y", date_loc) as year
                FROM xisf_files
                WHERE date_loc IS NOT NULL
                ORDER BY year DESC
            ''')
            return [row[0] for row in cursor.fetchall()]

    def get_activity_data_for_year(self, year: str) -> Dict[str, float]:
        """
        Get activity data (total exposure hours) for each date in a year.

        Args:
            year: Year as string (e.g., '2024')

        Returns:
            Dictionary mapping date strings to total exposure hours
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date_loc, SUM(exposure) / 3600.0 as total_hours
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
                GROUP BY date_loc
            ''', (year,))
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_analytics_summary(self, year: Optional[str] = None) -> Dict[str, Any]:
        """
        Get analytics summary statistics.

        Args:
            year: Optional year to filter by

        Returns:
            Dictionary with sessions count, total_hours, avg_hours, etc.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clause = ''
            params = []
            if year:
                where_clause = 'WHERE strftime("%Y", date_loc) = ?'
                params = [year]

            # Get sessions (distinct dates with light frames)
            cursor.execute(f'''
                SELECT COUNT(DISTINCT date_loc)
                FROM xisf_files
                {where_clause}
                    AND imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
            ''', params)
            sessions_count = cursor.fetchone()[0]

            # Get total exposure hours
            cursor.execute(f'''
                SELECT SUM(exposure) / 3600.0
                FROM xisf_files
                {where_clause}
                    AND imagetyp LIKE '%Light%'
                    AND exposure IS NOT NULL
            ''', params)
            total_hours = cursor.fetchone()[0] or 0.0

            avg_hours = total_hours / sessions_count if sessions_count > 0 else 0.0

            return {
                'sessions_count': sessions_count,
                'total_hours': total_hours,
                'avg_hours': avg_hours
            }
