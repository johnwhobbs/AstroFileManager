"""
Analytics tab UI for the AstroFileManager application.

Displays imaging activity analytics with:
- Yearly statistics (sessions, hours, streaks)
- GitHub-style activity heatmap calendar
- Theme-aware styling
"""

import sqlite3
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QMessageBox
)


class AnalyticsTab(QWidget):
    """Analytics tab widget showing imaging activity statistics and heatmap."""

    def __init__(self, db_path: str, settings: QSettings):
        """Initialize the analytics tab.

        Args:
            db_path: Path to the SQLite database
            settings: QSettings instance for application settings
        """
        super().__init__()
        self.db_path = db_path
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        """Create the analytics tab with activity heatmap"""
        layout = QVBoxLayout(self)

        # Year selector
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

        # Statistics cards
        self.analytics_stats_widget = QWidget()
        self.analytics_stats_layout = QHBoxLayout(self.analytics_stats_widget)
        self.analytics_stats_layout.setSpacing(10)
        layout.addWidget(self.analytics_stats_widget)

        # Heatmap container
        heatmap_label = QLabel("Imaging Activity Calendar")
        heatmap_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(heatmap_label)

        self.heatmap_widget = QWidget()
        self.heatmap_layout = QHBoxLayout(self.heatmap_widget)
        self.heatmap_layout.setSpacing(3)
        self.heatmap_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.heatmap_widget)

        # Legend
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

        layout.addStretch()

    def get_heatmap_color_style(self, level):
        """Get stylesheet for heatmap cell based on activity level"""
        # Check current theme
        current_theme = self.settings.value('theme', 'dark')

        if current_theme == 'dark':
            # Dark theme colors - green scale
            colors = {
                0: "#2d2d2d",
                1: "#0e4429",
                2: "#006d32",
                3: "#26a641",
                4: "#39d353"
            }
        else:
            # Standard theme colors - blue scale
            colors = {
                0: "#ebedf0",
                1: "#9be9a8",
                2: "#40c463",
                3: "#30a14e",
                4: "#216e39"
            }

        return f"background-color: {colors.get(level, colors[0])}; border-radius: 2px;"

    def refresh_analytics(self):
        """Refresh the analytics view"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get available years
            cursor.execute('SELECT DISTINCT strftime("%Y", date_loc) as year FROM xisf_files WHERE date_loc IS NOT NULL ORDER BY year DESC')
            years = [row[0] for row in cursor.fetchall()]

            # Populate year combo if empty or update selection
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

            # Get activity data for the selected year
            cursor.execute('''
                SELECT
                    date_loc,
                    SUM(exposure) / 3600.0 as hours
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
                    AND exposure IS NOT NULL
                    AND (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
                GROUP BY date_loc
            ''', (selected_year,))

            activity_data = {row[0]: row[1] for row in cursor.fetchall()}

            # Calculate statistics
            cursor.execute('''
                SELECT COUNT(DISTINCT date_loc) as sessions
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
            ''', (selected_year,))
            total_sessions = cursor.fetchone()[0]

            cursor.execute('''
                SELECT SUM(exposure) / 3600.0 as total_hours
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND exposure IS NOT NULL
                    AND (imagetyp = 'Light Frame' OR imagetyp LIKE '%Light%')
            ''', (selected_year,))
            total_hours = cursor.fetchone()[0] or 0

            avg_hours = total_hours / total_sessions if total_sessions > 0 else 0

            # Most active month
            cursor.execute('''
                SELECT
                    strftime("%m", date_loc) as month,
                    COUNT(DISTINCT date_loc) as sessions
                FROM xisf_files
                WHERE strftime("%Y", date_loc) = ?
                    AND date_loc IS NOT NULL
                GROUP BY month
                ORDER BY sessions DESC
                LIMIT 1
            ''', (selected_year,))

            most_active = cursor.fetchone()
            if most_active:
                month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                most_active_month = month_names[int(most_active[0])]
                sessions_in_month = most_active[1]
            else:
                most_active_month = 'N/A'
                sessions_in_month = 0

            # Calculate longest streak
            all_dates = sorted([d for d in activity_data.keys()])
            longest_streak = 0
            current_streak = 0

            for i, date in enumerate(all_dates):
                if i == 0:
                    current_streak = 1
                else:
                    prev_date = datetime.strptime(all_dates[i-1], '%Y-%m-%d')
                    curr_date = datetime.strptime(date, '%Y-%m-%d')
                    if (curr_date - prev_date).days == 1:
                        current_streak += 1
                    else:
                        longest_streak = max(longest_streak, current_streak)
                        current_streak = 1
            longest_streak = max(longest_streak, current_streak)

            # Days since last session
            cursor.execute('''
                SELECT MAX(date_loc)
                FROM xisf_files
                WHERE date_loc IS NOT NULL
            ''')
            last_session = cursor.fetchone()[0]
            if last_session:
                last_date = datetime.strptime(last_session, '%Y-%m-%d')
                today = datetime.now()
                days_since = (today - last_date).days
            else:
                days_since = 0

            conn.close()

            # Update statistics cards
            self.update_analytics_stats(
                total_sessions, total_hours, avg_hours,
                longest_streak, most_active_month, sessions_in_month, days_since
            )

            # Update heatmap
            self.update_heatmap(selected_year, activity_data)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to refresh analytics: {e}')

    def update_analytics_stats(self, sessions, total_hours, avg_hours, streak, month, month_sessions, days_since):
        """Update the analytics statistics cards"""
        # Clear existing cards
        while self.analytics_stats_layout.count():
            child = self.analytics_stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Check current theme
        current_theme = self.settings.value('theme', 'dark')

        if current_theme == 'dark':
            card_bg = "#2d2d2d"
            value_color = "#39d353"
            label_color = "#888"
        else:
            card_bg = "#f6f8fa"
            value_color = "#0969da"
            label_color = "#57606a"

        stats = [
            (sessions, "Clear Nights Imaged"),
            (f"{total_hours:.1f}", "Total Hours"),
            (f"{avg_hours:.1f}", "Avg Hours/Session"),
            (streak, "Longest Streak (days)"),
            (month, "Most Active Month"),
            (month_sessions, f"Sessions in {month}"),
            (days_since, "Days Since Last Session")
        ]

        for value, label in stats:
            card = QWidget()
            card.setStyleSheet(f"background-color: {card_bg}; border-radius: 8px; padding: 10px; border: 1px solid #d0d7de;")
            card_layout = QVBoxLayout(card)

            value_label = QLabel(str(value))
            value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {value_color};")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            desc_label = QLabel(label)
            desc_label.setStyleSheet(f"font-size: 11px; color: {label_color};")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)

            card_layout.addWidget(value_label)
            card_layout.addWidget(desc_label)

            self.analytics_stats_layout.addWidget(card)

    def update_heatmap(self, year, activity_data):
        """Update the heatmap visualization"""
        # Clear existing heatmap
        while self.heatmap_layout.count():
            child = self.heatmap_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        start_date = datetime(int(year), 1, 1)
        end_date = datetime(int(year), 12, 31)

        # Start on Sunday before the year starts
        first_sunday = start_date - timedelta(days=start_date.weekday() + 1 if start_date.weekday() != 6 else 0)

        current_date = first_sunday
        current_week = None

        while current_date <= end_date:
            # Start new week column on Sunday
            if current_date.weekday() == 6:  # Sunday
                if current_week:
                    self.heatmap_layout.addWidget(current_week)
                current_week = QWidget()
                week_layout = QVBoxLayout(current_week)
                week_layout.setSpacing(3)
                week_layout.setContentsMargins(0, 0, 0, 0)

            # Create day cell
            cell = QLabel()
            cell.setFixedSize(15, 15)

            date_str = current_date.strftime('%Y-%m-%d')

            if current_date < start_date:
                # Days before year starts - invisible
                cell.setStyleSheet("background-color: transparent;")
            else:
                hours = activity_data.get(date_str, 0)
                level = self.get_activity_level(hours)
                cell.setStyleSheet(self.get_heatmap_color_style(level))
                cell.setToolTip(f"{current_date.strftime('%b %d, %Y')}\n{hours:.1f} hours")

            week_layout.addWidget(cell)
            current_date += timedelta(days=1)

        # Add final week
        if current_week:
            self.heatmap_layout.addWidget(current_week)

    def get_activity_level(self, hours):
        """Determine activity level based on hours"""
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
