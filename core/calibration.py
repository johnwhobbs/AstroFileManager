"""
Calibration frame matching logic for AstroFileManager.

This module handles matching calibration frames (darks, flats, bias) to light frames
based on exposure, temperature, binning, and other criteria.
"""

from typing import Dict, Any, Tuple, Optional
from PyQt6.QtGui import QColor


# Import constants - these will be imported from the main module
# For now, we'll reference them directly from the constants module when integrated
# Using default values here for the module to be self-contained during development


class CalibrationMatcher:
    """
    Match calibration frames to light frames based on exposure, temperature, and binning.

    This class encapsulates all the business logic for finding matching calibration frames
    and determining session completeness.
    """

    def __init__(self, db_manager, include_masters: bool = True,
                 temp_tolerance_darks: float = 1.0,
                 temp_tolerance_flats: float = 3.0,
                 temp_tolerance_bias: float = 1.0,
                 exposure_tolerance: float = 0.1,
                 min_frames_recommended: int = 20,
                 min_frames_acceptable: int = 10):
        """
        Initialize calibration matcher.

        Args:
            db_manager: DatabaseManager instance
            include_masters: Whether to include master frames in counts
            temp_tolerance_darks: Temperature tolerance for dark frames (°C)
            temp_tolerance_flats: Temperature tolerance for flat frames (°C)
            temp_tolerance_bias: Temperature tolerance for bias frames (°C)
            exposure_tolerance: Exposure tolerance (seconds)
            min_frames_recommended: Recommended minimum number of frames
            min_frames_acceptable: Acceptable minimum number of frames
        """
        self.db = db_manager
        self.include_masters = include_masters
        self.temp_tolerance_darks = temp_tolerance_darks
        self.temp_tolerance_flats = temp_tolerance_flats
        self.temp_tolerance_bias = temp_tolerance_bias
        self.exposure_tolerance = exposure_tolerance
        self.min_frames_recommended = min_frames_recommended
        self.min_frames_acceptable = min_frames_acceptable

    def find_matching_darks(self, exposure: float, temp: Optional[float],
                           xbin: int, ybin: int) -> Dict[str, Any]:
        """
        Find matching dark frames with temperature tolerance.

        Args:
            exposure: Exposure time in seconds
            temp: CCD temperature in °C
            xbin: X binning
            ybin: Y binning

        Returns:
            Dictionary with count, master_count, avg_temp, quality, display, has_frames, exposure
        """
        # Temperature tolerance
        temp_min = temp - self.temp_tolerance_darks if temp else -999
        temp_max = temp + self.temp_tolerance_darks if temp else 999

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Find regular darks
            cursor.execute(f'''
                SELECT COUNT(*), AVG(ccd_temp)
                FROM xisf_files
                WHERE imagetyp LIKE '%Dark%'
                    AND imagetyp NOT LIKE '%Master%'
                    AND ABS(exposure - ?) < {self.exposure_tolerance}
                    AND ccd_temp BETWEEN ? AND ?
                    AND xbinning = ?
                    AND ybinning = ?
            ''', (exposure, temp_min, temp_max, xbin, ybin))

            dark_count, dark_temp = cursor.fetchone()
            dark_count = dark_count or 0

            # Find master darks
            master_count = 0
            if self.include_masters:
                cursor.execute(f'''
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Master%'
                        AND imagetyp LIKE '%Dark%'
                        AND ABS(exposure - ?) < {self.exposure_tolerance}
                        AND ccd_temp BETWEEN ? AND ?
                        AND xbinning = ?
                        AND ybinning = ?
                ''', (exposure, temp_min, temp_max, xbin, ybin))

                master_count = cursor.fetchone()[0] or 0

            # Calculate quality score (0-100)
            quality = min(100, (dark_count / self.min_frames_recommended) * 100) if dark_count > 0 else 0

            # Determine display text and status
            if master_count > 0:
                display = f"✓ {dark_count} + {master_count} Master"
                has_frames = True
            elif dark_count >= self.min_frames_acceptable:
                display = f"✓ {dark_count} frames"
                has_frames = True
            elif dark_count > 0:
                display = f"⚠ {dark_count} frames (need {self.min_frames_acceptable}+)"
                has_frames = True
            else:
                display = "✗ Missing"
                has_frames = False

            return {
                'count': dark_count,
                'master_count': master_count,
                'avg_temp': dark_temp,
                'quality': quality,
                'display': display,
                'has_frames': has_frames,
                'exposure': exposure
            }

    def find_matching_bias(self, temp: Optional[float], xbin: int, ybin: int) -> Dict[str, Any]:
        """
        Find matching bias frames with temperature tolerance.

        Args:
            temp: CCD temperature in °C
            xbin: X binning
            ybin: Y binning

        Returns:
            Dictionary with count, master_count, avg_temp, quality, display, has_frames
        """
        # Temperature tolerance
        temp_min = temp - self.temp_tolerance_bias if temp else -999
        temp_max = temp + self.temp_tolerance_bias if temp else 999

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Find regular bias
            cursor.execute('''
                SELECT COUNT(*), AVG(ccd_temp)
                FROM xisf_files
                WHERE imagetyp LIKE '%Bias%'
                    AND imagetyp NOT LIKE '%Master%'
                    AND ccd_temp BETWEEN ? AND ?
                    AND xbinning = ?
                    AND ybinning = ?
            ''', (temp_min, temp_max, xbin, ybin))

            bias_count, bias_temp = cursor.fetchone()
            bias_count = bias_count or 0

            # Find master bias
            master_count = 0
            if self.include_masters:
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Master%'
                        AND imagetyp LIKE '%Bias%'
                        AND ccd_temp BETWEEN ? AND ?
                        AND xbinning = ?
                        AND ybinning = ?
                ''', (temp_min, temp_max, xbin, ybin))

                master_count = cursor.fetchone()[0] or 0

            # Calculate quality score (0-100)
            quality = min(100, (bias_count / self.min_frames_recommended) * 100) if bias_count > 0 else 0

            # Determine display text and status
            if master_count > 0:
                display = f"✓ {bias_count} + {master_count} Master"
                has_frames = True
            elif bias_count >= self.min_frames_acceptable:
                display = f"✓ {bias_count} frames"
                has_frames = True
            elif bias_count > 0:
                display = f"⚠ {bias_count} frames (need {self.min_frames_acceptable}+)"
                has_frames = True
            else:
                display = "✗ Missing"
                has_frames = False

            return {
                'count': bias_count,
                'master_count': master_count,
                'avg_temp': bias_temp,
                'quality': quality,
                'display': display,
                'has_frames': has_frames
            }

    def find_matching_flats(self, filter_name: Optional[str], temp: Optional[float],
                           xbin: int, ybin: int, session_date: str) -> Dict[str, Any]:
        """
        Find matching flat frames with temperature tolerance and exact date match.

        Args:
            filter_name: Filter name
            temp: CCD temperature in °C
            xbin: X binning
            ybin: Y binning
            session_date: Session date (YYYY-MM-DD)

        Returns:
            Dictionary with count, master_count, avg_temp, quality, display, has_frames, filter
        """
        # Temperature tolerance for flats
        temp_min = temp - self.temp_tolerance_flats if temp else -999
        temp_max = temp + self.temp_tolerance_flats if temp else 999

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Find regular flats (exact date match)
            cursor.execute('''
                SELECT COUNT(*), AVG(ccd_temp)
                FROM xisf_files
                WHERE imagetyp LIKE '%Flat%'
                    AND imagetyp NOT LIKE '%Master%'
                    AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                    AND ccd_temp BETWEEN ? AND ?
                    AND xbinning = ?
                    AND ybinning = ?
                    AND date_loc = ?
            ''', (filter_name, filter_name, temp_min, temp_max, xbin, ybin, session_date))

            flat_count, flat_temp = cursor.fetchone()
            flat_count = flat_count or 0

            # Find master flats (exact date match)
            master_count = 0
            if self.include_masters:
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM xisf_files
                    WHERE imagetyp LIKE '%Master%'
                        AND imagetyp LIKE '%Flat%'
                        AND (filter = ? OR (filter IS NULL AND ? IS NULL))
                        AND ccd_temp BETWEEN ? AND ?
                        AND xbinning = ?
                        AND ybinning = ?
                        AND date_loc = ?
                ''', (filter_name, filter_name, temp_min, temp_max, xbin, ybin, session_date))

                master_count = cursor.fetchone()[0] or 0

            # Calculate quality score (0-100)
            quality = min(100, (flat_count / self.min_frames_recommended) * 100) if flat_count > 0 else 0

            # Determine display text and status
            if master_count > 0:
                display = f"✓ {flat_count} + {master_count} Master"
                has_frames = True
            elif flat_count >= self.min_frames_acceptable:
                display = f"✓ {flat_count} frames"
                has_frames = True
            elif flat_count > 0:
                display = f"⚠ {flat_count} frames (need {self.min_frames_acceptable}+)"
                has_frames = True
            else:
                display = "✗ Missing"
                has_frames = False

            return {
                'count': flat_count,
                'master_count': master_count,
                'avg_temp': flat_temp,
                'quality': quality,
                'display': display,
                'has_frames': has_frames,
                'filter': filter_name
            }

    def calculate_session_status(self, darks_info: Dict, bias_info: Dict,
                                 flats_info: Dict) -> Tuple[str, QColor]:
        """
        Calculate overall session status.

        Args:
            darks_info: Dark frames information from find_matching_darks()
            bias_info: Bias frames information from find_matching_bias()
            flats_info: Flat frames information from find_matching_flats()

        Returns:
            Tuple of (status_text, color)
        """
        has_darks = darks_info['has_frames']
        has_bias = bias_info['has_frames']
        has_flats = flats_info['has_frames']

        # Check if we have master frames
        has_master = (darks_info['master_count'] > 0 or
                     bias_info['master_count'] > 0 or
                     flats_info['master_count'] > 0)

        if has_darks and has_bias and has_flats:
            if has_master:
                return 'Complete', QColor(0, 150, 255)  # Blue for complete with masters
            else:
                return 'Complete', QColor(0, 200, 0)  # Green for complete
        elif not has_darks and not has_bias and not has_flats:
            return 'Missing', QColor(200, 0, 0)  # Red for missing all
        else:
            return 'Partial', QColor(255, 165, 0)  # Orange for partial

    def generate_recommendations(self, session_data: Dict[str, Any]) -> str:
        """
        Generate recommendations for missing or incomplete calibration frames.

        Args:
            session_data: Dictionary containing session information including darks, bias, flats

        Returns:
            Multi-line string with recommendations
        """
        recommendations = []

        darks = session_data['darks']
        bias = session_data['bias']
        flats = session_data['flats']

        if not darks['has_frames']:
            recommendations.append(f"• Capture dark frames: {session_data['avg_exposure']:.1f}s exposure at ~{session_data['avg_temp']:.0f}°C, {session_data['xbinning']}x{session_data['ybinning']} binning (minimum {self.min_frames_acceptable}, recommended {self.min_frames_recommended}+)")
        elif darks['count'] < self.min_frames_acceptable and darks['master_count'] == 0:
            recommendations.append(f"• Add more dark frames: Currently {darks['count']}, need at least {self.min_frames_acceptable} for good calibration")

        if not bias['has_frames']:
            recommendations.append(f"• Capture bias frames: ~{session_data['avg_temp']:.0f}°C, {session_data['xbinning']}x{session_data['ybinning']} binning (minimum {self.min_frames_acceptable}, recommended {self.min_frames_recommended}+)")
        elif bias['count'] < self.min_frames_acceptable and bias['master_count'] == 0:
            recommendations.append(f"• Add more bias frames: Currently {bias['count']}, need at least {self.min_frames_acceptable} for good calibration")

        if not flats['has_frames']:
            filter_name = session_data['filter'] or 'No Filter'
            recommendations.append(f"• Capture flat frames: {filter_name}, ~{session_data['avg_temp']:.0f}°C, {session_data['xbinning']}x{session_data['ybinning']} binning (minimum {self.min_frames_acceptable}, recommended {self.min_frames_recommended}+)")
        elif flats['count'] < self.min_frames_acceptable and flats['master_count'] == 0:
            recommendations.append(f"• Add more flat frames: Currently {flats['count']}, need at least {self.min_frames_acceptable} for good calibration")

        if not recommendations:
            if darks['master_count'] > 0 or bias['master_count'] > 0 or flats['master_count'] > 0:
                recommendations.append("✓ Session has master calibration frames available")
            else:
                recommendations.append("✓ All calibration frames are present")
                recommendations.append("\nOptional improvements:")
                if darks['count'] < self.min_frames_recommended:
                    recommendations.append(f"• Consider adding more darks (currently {darks['count']}, recommended {self.min_frames_recommended}+)")
                if bias['count'] < self.min_frames_recommended:
                    recommendations.append(f"• Consider adding more bias (currently {bias['count']}, recommended {self.min_frames_recommended}+)")
                if flats['count'] < self.min_frames_recommended:
                    recommendations.append(f"• Consider adding more flats (currently {flats['count']}, recommended {self.min_frames_recommended}+)")

        return '\n'.join(recommendations)
