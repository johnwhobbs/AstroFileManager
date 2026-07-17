"""
Analytics tab UI for the AstroFileManager application.

Displays imaging activity analytics with:
- Yearly statistics (sessions, hours, streaks)
- GitHub-style activity heatmap calendar
- Frame quality metrics summary (FWHM, SNR, Eccentricity, approval rate)
- Quality breakdown by filter
- FWHM trend over time by imaging session
- Theme-aware styling
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QMessageBox, QScrollArea, QFrame
)


class AnalyticsTab(QWidget):
    """Analytics tab widget showing imaging activity statistics and quality dashboards."""

    def __init__(self, db_path: str, settings: QSettings) -> None:
        """Initialize the analytics tab.

        Args:
            db_path: Path to the SQLite database
            settings: QSettings instance for application settings
        """
        super().__init__()
        self.db_path = db_path
        self.settings = settings
        self.init_ui()

    def init_ui(self) -> None:
        """Create the analytics tab with activity heatmap and quality dashboards."""
        # Outer layout holds just the scroll area so all content is reachable
        # on smaller screens
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area makes the tab scrollable when content exceeds window height
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # All visible content lives inside this widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # ── Year Selector ──────────────────────────────────────────────────────
        year_layout = QHBoxLayout()
        year_label = QLabel("Year:")
        self.year_combo = QComboBox()
        self.year_combo.currentTextChanged.connect(self.refresh_analytics)
        year_layout.addWidget(year_label)
        year_layout.addWidget(self.year_combo)
        year_layout.addStretch()

        refresh_analytics_btn = QPushButton('Refresh')
        refresh_analytics_btn.clicked.connect(self.refresh_analytics)
        year_layout.addWidget(refresh_analytics_btn)
        layout.addLayout(year_layout)

        # ── Section 1: Imaging Activity ────────────────────────────────────────
        activity_section_label = QLabel("Imaging Activity")
        activity_section_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-top: 5px;"
        )
        layout.addWidget(activity_section_label)

        # Row of activity statistics cards
        self.analytics_stats_widget = QWidget()
        self.analytics_stats_layout = QHBoxLayout(self.analytics_stats_widget)
        self.analytics_stats_layout.setSpacing(10)
        layout.addWidget(self.analytics_stats_widget)

        # GitHub-style activity calendar heatmap
        heatmap_label = QLabel("Imaging Activity Calendar")
        heatmap_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; margin-top: 10px;"
        )
        layout.addWidget(heatmap_label)

        self.heatmap_widget = QWidget()
        self.heatmap_layout = QHBoxLayout(self.heatmap_widget)
        self.heatmap_layout.setSpacing(3)
        self.heatmap_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.heatmap_widget)

        # Heatmap colour legend
        legend_layout = QHBoxLayout()
        legend_layout.addStretch()
        legend_layout.addWidget(QLabel("Less"))
        for level in range(5):
            legend_cell = QLabel()
            legend_cell.setFixedSize(15, 15)
            legend_cell.setStyleSheet(self.get_heatmap_color_style(level))
            legend_layout.addWidget(legend_cell)
        legend_layout.addWidget(QLabel("More"))
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        layout.addWidget(self._make_separator())

        # ── Section 2: Frame Quality Summary ──────────────────────────────────
        quality_label = QLabel("Frame Quality Summary")
        quality_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-top: 5px;"
        )
        layout.addWidget(quality_label)

        # Explanatory note for users who have not yet imported quality data
        quality_note = QLabel(
            "Statistics for light frames with quality data "
            "(imported from PixInsight SubFrame Selector via the Projects tab)"
        )
        quality_note.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(quality_note)

        # Row of quality statistics cards
        self.quality_stats_widget = QWidget()
        self.quality_stats_layout = QHBoxLayout(self.quality_stats_widget)
        self.quality_stats_layout.setSpacing(10)
        layout.addWidget(self.quality_stats_widget)

        layout.addWidget(self._make_separator())

        # ── Section 3: Quality by Filter ──────────────────────────────────────
        filter_label = QLabel("Quality by Filter")
        filter_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-top: 5px;"
        )
        layout.addWidget(filter_label)

        # Container whose layout is rebuilt on every refresh
        self.filter_quality_widget = QWidget()
        self.filter_quality_layout = QVBoxLayout(self.filter_quality_widget)
        self.filter_quality_layout.setSpacing(1)
        layout.addWidget(self.filter_quality_widget)

        layout.addWidget(self._make_separator())

        # ── Section 4: FWHM Trend by Session ──────────────────────────────────
        fwhm_label = QLabel("FWHM Trend by Session")
        fwhm_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-top: 5px;"
        )
        layout.addWidget(fwhm_label)

        fwhm_note = QLabel(
            "Average FWHM per imaging session  "
            "(lower = sharper stars = better seeing conditions)"
        )
        fwhm_note.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(fwhm_note)

        # Container whose layout is rebuilt on every refresh
        self.fwhm_trend_widget = QWidget()
        self.fwhm_trend_layout = QVBoxLayout(self.fwhm_trend_widget)
        self.fwhm_trend_layout.setSpacing(1)
        layout.addWidget(self.fwhm_trend_widget)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

    # ──────────────────────────────────────────────────────────────────────────
    # Helper / factory methods
    # ──────────────────────────────────────────────────────────────────────────

    def _make_separator(self) -> QFrame:
        """Create a horizontal separator line.

        Returns:
            QFrame styled as a horizontal rule
        """
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

    def _make_stat_card(self, value: str, label: str, card_bg: str,
                        value_color: str, label_color: str) -> QWidget:
        """Create a statistics display card widget.

        Each card shows a large bold value with a smaller description label
        beneath it, matching the style used across the existing analytics section.

        Args:
            value: The main value to display (large, bold text)
            label: Description label shown below the value
            card_bg: Background colour for the card
            value_color: Colour for the value text
            label_color: Colour for the label text

        Returns:
            QWidget styled as a stats card
        """
        card = QWidget()
        card.setStyleSheet(
            f"background-color: {card_bg}; border-radius: 8px; "
            f"padding: 10px; border: 1px solid #d0d7de;"
        )
        card_layout = QVBoxLayout(card)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {value_color};"
        )
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_lbl = QLabel(label)
        desc_lbl.setStyleSheet(f"font-size: 11px; color: {label_color};")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)

        card_layout.addWidget(value_lbl)
        card_layout.addWidget(desc_lbl)
        return card

    def _make_table_cell(self, text: str, color: str,
                         min_width: int = 90) -> QLabel:
        """Create a centred, colour-coded table cell label.

        Args:
            text: Cell text content
            color: CSS colour string for the text
            min_width: Minimum cell width in pixels

        Returns:
            QLabel styled as a table cell
        """
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setMinimumWidth(min_width)
        return lbl

    def _get_quality_color(self, metric: str, value: float) -> str:
        """Return a colour string based on metric quality thresholds.

        For FWHM and eccentricity, lower values are better.
        For SNR weight, higher values are better.

        Thresholds are based on common PixInsight SubFrame Selector guidelines:
        - FWHM (arcseconds): < 2 excellent, 2–4 acceptable, > 4 poor
        - Eccentricity (0–1 ratio): < 0.4 excellent, 0.4–0.6 acceptable, > 0.6 poor
        - SNR weight (0–1 scale): > 0.7 excellent, 0.4–0.7 acceptable, < 0.4 poor

        Args:
            metric: One of 'fwhm', 'eccentricity', or 'snr'
            value: The metric value to evaluate

        Returns:
            CSS colour string — green = good, orange = average, red = poor
        """
        if metric == 'fwhm':
            if value < 2.0:
                return "#39d353"   # Green — excellent
            elif value < 4.0:
                return "#f0a500"   # Orange — acceptable
            else:
                return "#e05050"   # Red — poor
        elif metric == 'eccentricity':
            if value < 0.4:
                return "#39d353"
            elif value < 0.6:
                return "#f0a500"
            else:
                return "#e05050"
        elif metric == 'snr':
            if value > 0.7:
                return "#39d353"
            elif value > 0.4:
                return "#f0a500"
            else:
                return "#e05050"
        return "#888888"

    def _get_theme_colors(self) -> dict:
        """Return a colour palette dict that matches the current app theme.

        Returns:
            Dictionary with keys:
                card_bg, value_color, label_color,
                header_bg, row_bg, row_bg_alt, text_color, header_color
        """
        current_theme = self.settings.value('theme', 'dark')
        if current_theme == 'dark':
            return {
                'card_bg': "#2d2d2d",
                'value_color': "#39d353",
                'label_color': "#888",
                'header_bg': "#1a1a2e",
                'row_bg': "#252525",
                'row_bg_alt': "#2d2d2d",
                'text_color': "#ffffff",
                'header_color': "#aaaaaa",
            }
        else:
            return {
                'card_bg': "#f6f8fa",
                'value_color': "#0969da",
                'label_color': "#57606a",
                'header_bg': "#eaeef2",
                'row_bg': "#ffffff",
                'row_bg_alt': "#f6f8fa",
                'text_color': "#24292e",
                'header_color': "#57606a",
            }

    # ──────────────────────────────────────────────────────────────────────────
    # Heatmap colour helpers (unchanged from original)
    # ──────────────────────────────────────────────────────────────────────────

    def get_heatmap_color_style(self, level: int) -> str:
        """Get the CSS stylesheet for a heatmap cell based on its activity level.

        Args:
            level: Activity level 0–4 (0 = none, 4 = most active)

        Returns:
            CSS stylesheet string for the cell background colour
        """
        current_theme = self.settings.value('theme', 'dark')
        if current_theme == 'dark':
            # Green scale matching the GitHub contribution graph dark palette
            colors = {
                0: "#2d2d2d",
                1: "#0e4429",
                2: "#006d32",
                3: "#26a641",
                4: "#39d353"
            }
        else:
            # Blue-green scale for the light/standard palette
            colors = {
                0: "#ebedf0",
                1: "#9be9a8",
                2: "#40c463",
                3: "#30a14e",
                4: "#216e39"
            }
        return f"background-color: {colors.get(level, colors[0])}; border-radius: 2px;"

    def get_activity_level(self, hours: float) -> int:
        """Determine the heatmap activity level based on imaging hours.

        Args:
            hours: Total exposure hours accumulated on a single date

        Returns:
            Activity level 0–4 (0 = none, 4 = most active)
        """
        if hours == 0:
            return 0
        elif hours < 2:
            return 1
        elif hours < 4:
            return 2
        elif hours < 6:
            return 3
        else:
            return 4

    # ──────────────────────────────────────────────────────────────────────────
    # Main refresh entry point
    # ──────────────────────────────────────────────────────────────────────────

    def refresh_analytics(self) -> None:
        """Refresh all analytics dashboards for the currently selected year.

        Fetches activity data plus quality metrics from the database and
        updates all four dashboard sections: activity stats, heatmap, quality
        summary, quality-by-filter table, and FWHM trend table.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Populate year combo box with available years
            cursor.execute(
                'SELECT DISTINCT strftime("%Y", date_loc) AS year '
                'FROM xisf_files WHERE date_loc IS NOT NULL ORDER BY year DESC'
            )
            years = [row[0] for row in cursor.fetchall()]
            current_year = self.year_combo.currentText()
            self.year_combo.blockSignals(True)
            self.year_combo.clear()
            if years:
                self.year_combo.addItems(years)
                if current_year in years:
                    self.year_combo.setCurrentText(current_year)
            self.year_combo.blockSignals(False)

            selected_year = self.year_combo.currentText()
            if not selected_year:
                conn.close()
                return

            # ── Activity data ──────────────────────────────────────────────────
            # Total exposure hours per date for the heatmap
            cursor.execute('''
                SELECT
                    date_loc,
                    SUM(exposure) / 3600.0 AS hours
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
                    AND exposure IS NOT NULL
                    AND (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                GROUP BY date_loc
            ''', (selected_year,))
            activity_data = {row[0]: row[1] for row in cursor.fetchall()}

            # Number of distinct nights with any imaging
            cursor.execute('''
                SELECT COUNT(DISTINCT date_loc)
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
            ''', (selected_year,))
            total_sessions = cursor.fetchone()[0]

            # Total light-frame exposure hours
            cursor.execute('''
                SELECT SUM(exposure) / 3600.0
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND exposure IS NOT NULL
                    AND (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
            ''', (selected_year,))
            total_hours = cursor.fetchone()[0] or 0
            avg_hours = total_hours / total_sessions if total_sessions > 0 else 0

            # Most active month by number of distinct nights
            cursor.execute('''
                SELECT
                    strftime("%m", date_loc) AS month,
                    COUNT(DISTINCT date_loc) AS sessions
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
                GROUP BY month
                ORDER BY sessions DESC
                LIMIT 1
            ''', (selected_year,))
            most_active = cursor.fetchone()
            if most_active:
                month_names = [
                    '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
                ]
                most_active_month = month_names[int(most_active[0])]
                sessions_in_month = most_active[1]
            else:
                most_active_month = 'N/A'
                sessions_in_month = 0

            # Longest consecutive-night imaging streak
            all_dates = sorted(activity_data.keys())
            longest_streak = current_streak = 0
            for i, date in enumerate(all_dates):
                if i == 0:
                    current_streak = 1
                else:
                    prev = datetime.strptime(all_dates[i - 1], '%Y-%m-%d')
                    curr = datetime.strptime(date, '%Y-%m-%d')
                    if (curr - prev).days == 1:
                        current_streak += 1
                    else:
                        longest_streak = max(longest_streak, current_streak)
                        current_streak = 1
            longest_streak = max(longest_streak, current_streak)

            # Days elapsed since the most recent session across all years
            cursor.execute(
                'SELECT MAX(date_loc) FROM xisf_files WHERE date_loc IS NOT NULL'
            )
            last_session = cursor.fetchone()[0]
            days_since = 0
            if last_session:
                days_since = (
                    datetime.now() - datetime.strptime(last_session, '%Y-%m-%d')
                ).days

            # ── Quality summary stats ──────────────────────────────────────────
            # Averages and counts for light frames that have FWHM data
            cursor.execute('''
                SELECT
                    AVG(fwhm),
                    AVG(snr),
                    AVG(eccentricity),
                    AVG(star_count),
                    COUNT(CASE WHEN approval_status = 'approved' THEN 1 END),
                    COUNT(CASE WHEN approval_status = 'rejected' THEN 1 END),
                    COUNT(*)
                FROM xisf_files
                WHERE (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                    AND strftime("%Y", date_loc) = ?
                    AND fwhm IS NOT NULL
            ''', (selected_year,))
            quality_row = cursor.fetchone()

            # ── Quality by filter ──────────────────────────────────────────────
            # Per-filter averages and approval stats (only graded frames)
            cursor.execute('''
                SELECT
                    COALESCE(filter, 'Unknown') AS filter,
                    AVG(fwhm),
                    AVG(snr),
                    AVG(eccentricity),
                    AVG(star_count),
                    COUNT(CASE WHEN approval_status = 'approved' THEN 1 END),
                    COUNT(*)
                FROM xisf_files
                WHERE (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                    AND strftime("%Y", date_loc) = ?
                    AND fwhm IS NOT NULL
                GROUP BY filter
                ORDER BY filter
            ''', (selected_year,))
            filter_rows = cursor.fetchall()

            # ── FWHM trend by session ──────────────────────────────────────────
            # One row per imaging date showing session-level quality metrics
            cursor.execute('''
                SELECT
                    date_loc,
                    AVG(fwhm),
                    AVG(snr),
                    COUNT(*),
                    COUNT(CASE WHEN approval_status = 'approved' THEN 1 END)
                FROM xisf_files
                WHERE (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                    AND strftime("%Y", date_loc) = ?
                    AND fwhm IS NOT NULL
                GROUP BY date_loc
                ORDER BY date_loc
            ''', (selected_year,))
            fwhm_rows = cursor.fetchall()

            conn.close()

            # Update all UI sections
            self.update_analytics_stats(
                total_sessions, total_hours, avg_hours,
                longest_streak, most_active_month, sessions_in_month, days_since
            )
            self.update_heatmap(selected_year, activity_data)
            self.update_quality_stats(quality_row)
            self.update_quality_by_filter(filter_rows)
            self.update_fwhm_trend(fwhm_rows)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh analytics: {e}')

    # ──────────────────────────────────────────────────────────────────────────
    # Section update methods
    # ──────────────────────────────────────────────────────────────────────────

    def update_analytics_stats(self, sessions: int, total_hours: float,
                               avg_hours: float, streak: int, month: str,
                               month_sessions: int, days_since: int) -> None:
        """Rebuild the imaging activity statistics cards.

        Args:
            sessions: Number of distinct imaging nights in the selected year
            total_hours: Total light-frame exposure hours for the year
            avg_hours: Average exposure hours per imaging session
            streak: Longest consecutive days with at least one imaging session
            month: Name of the most active month (e.g. 'Sep')
            month_sessions: Number of imaging nights in the most active month
            days_since: Days elapsed since the most recent session (any year)
        """
        # Remove all existing cards before rebuilding
        while self.analytics_stats_layout.count():
            child = self.analytics_stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        colors = self._get_theme_colors()

        stats = [
            (sessions, "Clear Nights Imaged"),
            (f"{total_hours:.1f}", "Total Hours"),
            (f"{avg_hours:.1f}", "Avg Hours/Session"),
            (streak, "Longest Streak (days)"),
            (month, "Most Active Month"),
            (month_sessions, f"Sessions in {month}"),
            (days_since, "Days Since Last Session"),
        ]

        for value, label in stats:
            card = self._make_stat_card(
                str(value), label,
                colors['card_bg'], colors['value_color'], colors['label_color']
            )
            self.analytics_stats_layout.addWidget(card)

    def update_quality_stats(self, quality_row: Optional[Tuple]) -> None:
        """Rebuild the frame quality summary cards.

        Displays aggregate quality metrics — avg FWHM, SNR, eccentricity,
        star count, approval rate, and total frames graded — for all light
        frames in the selected year that have quality data from SubFrame
        Selector. Each card's value is colour-coded against quality thresholds.

        Args:
            quality_row: Tuple from DB query:
                (avg_fwhm, avg_snr, avg_eccentricity, avg_stars,
                 approved_count, rejected_count, total_graded)
                or None when no quality data has been imported yet.
        """
        while self.quality_stats_layout.count():
            child = self.quality_stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        colors = self._get_theme_colors()

        # Guard: no quality data imported for this year
        if not quality_row or quality_row[6] == 0:
            msg = QLabel(
                "No quality data found for this year. "
                "Import a SubFrame Selector CSV via the Projects tab to see quality metrics."
            )
            msg.setStyleSheet("color: #888; font-style: italic; padding: 10px;")
            msg.setWordWrap(True)
            self.quality_stats_layout.addWidget(msg)
            return

        avg_fwhm, avg_snr, avg_eccentricity, avg_stars, approved, rejected, total = quality_row

        # Approval rate is calculated only over frames that have been graded
        graded = (approved or 0) + (rejected or 0)
        approval_rate = (approved / graded * 100) if graded > 0 else 0

        quality_cards = [
            (
                f"{avg_fwhm:.2f}\"" if avg_fwhm is not None else "N/A",
                "Avg FWHM",
                self._get_quality_color('fwhm', avg_fwhm)
                if avg_fwhm is not None else "#888"
            ),
            (
                f"{avg_snr:.3f}" if avg_snr is not None else "N/A",
                "Avg SNR Weight",
                self._get_quality_color('snr', avg_snr)
                if avg_snr is not None else "#888"
            ),
            (
                f"{avg_eccentricity:.3f}" if avg_eccentricity is not None else "N/A",
                "Avg Eccentricity",
                self._get_quality_color('eccentricity', avg_eccentricity)
                if avg_eccentricity is not None else "#888"
            ),
            (
                f"{int(avg_stars)}" if avg_stars is not None else "N/A",
                "Avg Star Count",
                "#39d353"
            ),
            (
                f"{approval_rate:.0f}%",
                "Approval Rate",
                "#39d353" if approval_rate >= 80
                else "#f0a500" if approval_rate >= 50
                else "#e05050"
            ),
            (
                str(total),
                "Frames Graded",
                colors['value_color']
            ),
        ]

        for value, label, value_color in quality_cards:
            card = self._make_stat_card(
                value, label,
                colors['card_bg'], value_color, colors['label_color']
            )
            self.quality_stats_layout.addWidget(card)

    def update_quality_by_filter(self, rows: List[Tuple]) -> None:
        """Rebuild the quality-by-filter breakdown table.

        Shows a colour-coded tabular summary with one row per optical filter,
        including average FWHM, SNR weight, eccentricity, total frame count,
        and approval percentage. Metric values are colour-coded against the
        quality thresholds defined in _get_quality_color().

        Args:
            rows: List of tuples from DB query, each containing:
                (filter, avg_fwhm, avg_snr, avg_eccentricity,
                 avg_stars, approved_count, total)
        """
        while self.filter_quality_layout.count():
            child = self.filter_quality_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not rows:
            msg = QLabel("No filter quality data available for this year.")
            msg.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
            self.filter_quality_layout.addWidget(msg)
            return

        colors = self._get_theme_colors()

        # Column definitions: (header text, min width in px)
        col_defs = [
            ("Filter", 120), ("Frames", 80), ("Approved", 80),
            ("Approval %", 90), ("Avg FWHM", 90),
            ("Avg SNR", 90), ("Avg Eccen.", 90),
        ]

        # Header row
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background-color: {colors['header_bg']};")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        for text, width in col_defs:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-weight: bold; color: {colors['header_color']}; font-size: 11px;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumWidth(width)
            header_layout.addWidget(lbl)
        self.filter_quality_layout.addWidget(header_widget)

        # One data row per filter
        for idx, row in enumerate(rows):
            filter_name, avg_fwhm, avg_snr, avg_eccentricity, avg_stars, approved, total = row
            approval_pct = (approved / total * 100) if total > 0 else 0

            # Alternate row background for readability
            bg = colors['row_bg'] if idx % 2 == 0 else colors['row_bg_alt']
            row_widget = QWidget()
            row_widget.setStyleSheet(f"background-color: {bg};")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(5, 3, 5, 3)

            row_layout.addWidget(
                self._make_table_cell(
                    filter_name or "Unknown", colors['text_color'], 120
                )
            )
            row_layout.addWidget(
                self._make_table_cell(str(int(total)), colors['text_color'])
            )
            row_layout.addWidget(
                self._make_table_cell(str(int(approved)), colors['text_color'])
            )
            row_layout.addWidget(self._make_table_cell(
                f"{approval_pct:.0f}%",
                "#39d353" if approval_pct >= 80
                else "#f0a500" if approval_pct >= 50
                else "#e05050"
            ))
            row_layout.addWidget(self._make_table_cell(
                f"{avg_fwhm:.2f}\"" if avg_fwhm is not None else "N/A",
                self._get_quality_color('fwhm', avg_fwhm)
                if avg_fwhm is not None else "#888"
            ))
            row_layout.addWidget(self._make_table_cell(
                f"{avg_snr:.3f}" if avg_snr is not None else "N/A",
                self._get_quality_color('snr', avg_snr)
                if avg_snr is not None else "#888"
            ))
            row_layout.addWidget(self._make_table_cell(
                f"{avg_eccentricity:.3f}" if avg_eccentricity is not None else "N/A",
                self._get_quality_color('eccentricity', avg_eccentricity)
                if avg_eccentricity is not None else "#888"
            ))
            self.filter_quality_layout.addWidget(row_widget)

    def update_fwhm_trend(self, rows: List[Tuple]) -> None:
        """Rebuild the FWHM-trend-by-session table.

        Shows a chronological list of imaging sessions with colour-coded FWHM
        and SNR values, plus approval counts. This helps astrophotographers
        identify their best and worst seeing nights at a glance.
        The session with the lowest average FWHM is labelled "(Best)".

        Args:
            rows: List of tuples from DB query, each containing:
                (date_loc, avg_fwhm, avg_snr, frame_count, approved_count)
        """
        while self.fwhm_trend_layout.count():
            child = self.fwhm_trend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not rows:
            msg = QLabel("No FWHM trend data available for this year.")
            msg.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
            self.fwhm_trend_layout.addWidget(msg)
            return

        colors = self._get_theme_colors()

        # Pre-compute the best (lowest) FWHM so we can highlight that session
        valid_fwhm = [r[1] for r in rows if r[1] is not None]
        best_fwhm = min(valid_fwhm) if valid_fwhm else None

        # Column definitions: (header text, min width in px)
        col_defs = [
            ("Session Date", 130), ("Avg FWHM", 90),
            ("Seeing Quality", 120), ("Avg SNR", 90),
            ("Frames Graded", 110), ("Approved", 90),
        ]

        # Header row
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background-color: {colors['header_bg']};")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        for text, width in col_defs:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-weight: bold; color: {colors['header_color']}; font-size: 11px;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumWidth(width)
            header_layout.addWidget(lbl)
        self.fwhm_trend_layout.addWidget(header_widget)

        # One data row per imaging session date
        for idx, row in enumerate(rows):
            date_loc, avg_fwhm, avg_snr, frame_count, approved_count = row

            if avg_fwhm is not None:
                fwhm_color = self._get_quality_color('fwhm', avg_fwhm)
                # Human-readable seeing quality label
                if avg_fwhm < 2.0:
                    quality_text = "Excellent"
                elif avg_fwhm < 3.0:
                    quality_text = "Good"
                elif avg_fwhm < 4.0:
                    quality_text = "Average"
                else:
                    quality_text = "Poor"
                # Mark the session with the best (lowest) FWHM this year
                if best_fwhm is not None and abs(avg_fwhm - best_fwhm) < 0.001:
                    quality_text += " (Best)"
            else:
                fwhm_color = "#888"
                quality_text = "N/A"

            # Alternate row background for readability
            bg = colors['row_bg'] if idx % 2 == 0 else colors['row_bg_alt']
            row_widget = QWidget()
            row_widget.setStyleSheet(f"background-color: {bg};")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(5, 3, 5, 3)

            row_layout.addWidget(
                self._make_table_cell(
                    date_loc or "Unknown", colors['text_color'], 130
                )
            )
            row_layout.addWidget(self._make_table_cell(
                f"{avg_fwhm:.2f}\"" if avg_fwhm is not None else "N/A",
                fwhm_color
            ))
            row_layout.addWidget(
                self._make_table_cell(quality_text, fwhm_color, 120)
            )
            row_layout.addWidget(self._make_table_cell(
                f"{avg_snr:.3f}" if avg_snr is not None else "N/A",
                self._get_quality_color('snr', avg_snr)
                if avg_snr is not None else "#888"
            ))
            row_layout.addWidget(
                self._make_table_cell(
                    str(int(frame_count)), colors['text_color'], 110
                )
            )
            row_layout.addWidget(
                self._make_table_cell(
                    str(int(approved_count or 0)), colors['text_color']
                )
            )
            self.fwhm_trend_layout.addWidget(row_widget)

    def update_heatmap(self, year: str, activity_data: Dict[str, float]) -> None:
        """Rebuild the GitHub-style activity calendar heatmap.

        Renders a grid where each cell is one day of the selected year.
        Cell colour intensity corresponds to total exposure hours that day.
        The grid starts on the Sunday before January 1 to align columns
        with calendar weeks.

        Args:
            year: Four-digit year string (e.g. '2024')
            activity_data: Dict mapping 'YYYY-MM-DD' strings to exposure hours
        """
        while self.heatmap_layout.count():
            child = self.heatmap_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        start_date = datetime(int(year), 1, 1)
        end_date = datetime(int(year), 12, 31)

        # Align to the Sunday immediately before (or on) January 1
        first_sunday = start_date - timedelta(
            days=start_date.weekday() + 1 if start_date.weekday() != 6 else 0
        )

        current_date = first_sunday
        current_week = None

        while current_date <= end_date:
            # Start a new week column on every Sunday
            if current_date.weekday() == 6:
                if current_week:
                    self.heatmap_layout.addWidget(current_week)
                current_week = QWidget()
                week_layout = QVBoxLayout(current_week)
                week_layout.setSpacing(3)
                week_layout.setContentsMargins(0, 0, 0, 0)

            # Create a 15×15 px coloured day cell
            cell = QLabel()
            cell.setFixedSize(15, 15)
            date_str = current_date.strftime('%Y-%m-%d')

            if current_date < start_date:
                # Padding days before year starts — render transparent
                cell.setStyleSheet("background-color: transparent;")
            else:
                hours = activity_data.get(date_str, 0)
                level = self.get_activity_level(hours)
                cell.setStyleSheet(self.get_heatmap_color_style(level))
                cell.setToolTip(
                    f"{current_date.strftime('%b %d, %Y')}\n{hours:.1f} hours"
                )

            week_layout.addWidget(cell)
            current_date += timedelta(days=1)

        # Add the final (possibly incomplete) week column
        if current_week:
            self.heatmap_layout.addWidget(current_week)
