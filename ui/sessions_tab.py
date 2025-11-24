"""
Sessions tab UI for AstroFileManager.

This module contains the SessionsTab class which handles session planning and
calibration frame analysis.
"""

import sqlite3
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
    QLabel, QTextEdit, QGroupBox, QComboBox, QRadioButton,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QSplitter, QProgressBar
)
from PyQt6.QtCore import Qt, QSettings

from core.database import DatabaseManager
from core.calibration import CalibrationMatcher
from ui.background_workers import SessionsLoaderWorker


class SessionsTab(QWidget):
    """Sessions tab for session planning and calibration analysis."""

    def __init__(self, db_path: str, db_manager: DatabaseManager,
                 calibration_matcher: CalibrationMatcher, settings: QSettings) -> None:
        """
        Initialize Sessions tab.

        Args:
            db_path: Path to SQLite database
            db_manager: DatabaseManager instance
            calibration_matcher: CalibrationMatcher instance
            settings: QSettings instance for saving/restoring UI state
        """
        super().__init__()
        self.db_path = db_path
        self.db = db_manager
        self.calibration = calibration_matcher
        self.settings = settings
        self.loader_worker = None  # Background thread for loading sessions

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Top controls section
        controls_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton('Refresh Sessions')
        refresh_btn.clicked.connect(self.refresh_sessions)
        controls_layout.addWidget(refresh_btn)

        # Status filter dropdown
        controls_layout.addWidget(QLabel('Status Filter:'))
        self.session_status_filter = QComboBox()
        self.session_status_filter.addItems(['All', 'Complete', 'Partial', 'Missing'])
        self.session_status_filter.currentTextChanged.connect(self.refresh_sessions)
        controls_layout.addWidget(self.session_status_filter)

        # Missing only checkbox
        self.missing_only_checkbox = QRadioButton('Missing Only')
        self.missing_only_checkbox.toggled.connect(self.refresh_sessions)
        controls_layout.addWidget(self.missing_only_checkbox)

        # Include masters checkbox
        self.include_masters_checkbox = QRadioButton('Include Masters')
        self.include_masters_checkbox.setChecked(True)
        self.include_masters_checkbox.toggled.connect(self.refresh_sessions)
        controls_layout.addWidget(self.include_masters_checkbox)

        # Export button
        export_btn = QPushButton('Export Report')
        export_btn.clicked.connect(self.export_session_report)
        controls_layout.addWidget(export_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Progress indicator for background loading
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(2)

        self.sessions_status_label = QLabel("")
        self.sessions_status_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        progress_layout.addWidget(self.sessions_status_label)

        self.sessions_progress = QProgressBar()
        self.sessions_progress.setRange(0, 0)  # Indeterminate progress
        self.sessions_progress.setTextVisible(False)
        self.sessions_progress.setMaximumHeight(3)  # Very slim progress bar
        progress_layout.addWidget(self.sessions_progress)

        progress_widget.hide()  # Hidden by default
        self.sessions_progress_widget = progress_widget
        layout.addWidget(progress_widget)

        # Statistics panel
        stats_group = QGroupBox("Session Statistics")
        stats_layout = QHBoxLayout()

        self.total_sessions_label = QLabel('Total Sessions: 0')
        stats_layout.addWidget(self.total_sessions_label)

        self.complete_sessions_label = QLabel('Complete: 0')
        stats_layout.addWidget(self.complete_sessions_label)

        self.partial_sessions_label = QLabel('Partial: 0')
        stats_layout.addWidget(self.partial_sessions_label)

        self.missing_sessions_label = QLabel('Missing: 0')
        stats_layout.addWidget(self.missing_sessions_label)

        self.completion_rate_label = QLabel('Completion Rate: 0%')
        stats_layout.addWidget(self.completion_rate_label)

        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Sessions tree widget
        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setColumnCount(9)
        self.sessions_tree.setHeaderLabels([
            'Session', 'Status', 'Light Frames', 'FWHM', 'SNR', 'Approved', 'Darks', 'Bias', 'Flats'
        ])
        self.sessions_tree.setColumnWidth(0, 250)
        self.sessions_tree.setColumnWidth(1, 100)
        self.sessions_tree.setColumnWidth(2, 120)
        self.sessions_tree.setColumnWidth(3, 80)   # FWHM
        self.sessions_tree.setColumnWidth(4, 80)   # SNR
        self.sessions_tree.setColumnWidth(5, 100)  # Approved
        self.sessions_tree.setColumnWidth(6, 150)  # Darks
        self.sessions_tree.setColumnWidth(7, 150)  # Bias
        self.sessions_tree.setColumnWidth(8, 150)  # Flats
        self.sessions_tree.itemClicked.connect(self.on_session_clicked)
        layout.addWidget(self.sessions_tree)

        # Session details and recommendations panel with resizable splitter
        details_group = QGroupBox("Session Details")
        details_layout = QVBoxLayout()

        # Create a vertical splitter for resizable panels
        self.details_splitter = QSplitter(Qt.Orientation.Vertical)

        # Session details panel
        self.session_details_text = QTextEdit()
        self.session_details_text.setReadOnly(True)
        self.details_splitter.addWidget(self.session_details_text)

        # Recommendations panel with label
        recommendations_widget = QWidget()
        rec_layout = QVBoxLayout(recommendations_widget)
        rec_layout.setContentsMargins(0, 0, 0, 0)
        rec_layout.addWidget(QLabel('Recommendations:'))
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setPlaceholderText('Recommendations will appear here...')
        rec_layout.addWidget(self.recommendations_text)

        self.details_splitter.addWidget(recommendations_widget)

        # Set initial proportions (200:150 ratio from original fixed heights)
        self.details_splitter.setSizes([200, 150])

        # Connect splitter movement to save settings
        self.details_splitter.splitterMoved.connect(self.save_splitter_state)

        details_layout.addWidget(self.details_splitter)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

    def refresh_sessions(self) -> None:
        """Refresh the sessions view using background thread (non-blocking)."""
        try:
            # Cancel any existing worker
            if self.loader_worker:
                if self.loader_worker.isRunning():
                    self.loader_worker.terminate()
                    self.loader_worker.wait()

                # Disconnect all signals from old worker to prevent stale data
                try:
                    self.loader_worker.progress_updated.disconnect()
                    self.loader_worker.data_ready.disconnect()
                    self.loader_worker.error_occurred.disconnect()
                    self.loader_worker.finished.disconnect()
                except TypeError:
                    # Signals were not connected or already disconnected
                    pass

                # Clean up old worker
                self.loader_worker.deleteLater()
                self.loader_worker = None

            # Show progress
            self.sessions_progress_widget.show()
            self.sessions_status_label.setText("Loading sessions...")
            self.sessions_tree.setEnabled(False)

            # Update calibration matcher settings before loading
            self.calibration.include_masters = self.include_masters_checkbox.isChecked()

            # Create and start worker
            self.loader_worker = SessionsLoaderWorker(self.db_path, self.calibration)
            self.loader_worker.progress_updated.connect(self._on_sessions_progress)
            self.loader_worker.data_ready.connect(self._on_sessions_data_ready)
            self.loader_worker.error_occurred.connect(self._on_sessions_error)
            self.loader_worker.finished.connect(self._on_sessions_finished)
            self.loader_worker.start()

        except Exception as e:
            self.sessions_progress_widget.hide()
            self.sessions_tree.setEnabled(True)
            QMessageBox.critical(self, 'Error', f'Failed to start sessions load: {e}')

    def _on_sessions_progress(self, message: str) -> None:
        """Update progress message."""
        self.sessions_status_label.setText(message)

    def _on_sessions_error(self, error_msg: str) -> None:
        """Handle worker error."""
        self.sessions_progress_widget.hide()
        self.sessions_tree.setEnabled(True)
        QMessageBox.critical(self, 'Error', error_msg)

    def _on_sessions_finished(self) -> None:
        """Hide progress when worker finishes."""
        self.sessions_progress_widget.hide()
        self.sessions_tree.setEnabled(True)

    def _on_sessions_data_ready(self, sessions: list, calib_cache: dict) -> None:
        """
        Build sessions tree from loaded data (runs on UI thread).

        Args:
            sessions: List of session data tuples
            calib_cache: Pre-loaded calibration data cache
        """
        try:
            self.sessions_tree.clear()

            # Statistics counters
            total_count = 0
            complete_count = 0
            partial_count = 0
            missing_count = 0

            for session_data in sessions:
                date, obj, filt, frame_count, avg_exp, avg_temp, xbin, ybin, avg_fwhm, avg_snr, approved_count, rejected_count = session_data

                # Find matching calibration frames from cache (no database queries)
                darks_info = self.calibration.find_matching_darks_from_cache(
                    avg_exp, avg_temp, xbin, ybin, calib_cache['darks'])
                bias_info = self.calibration.find_matching_bias_from_cache(
                    avg_temp, xbin, ybin, calib_cache['bias'])
                flats_info = self.calibration.find_matching_flats_from_cache(
                    filt, avg_temp, xbin, ybin, date, calib_cache['flats'])

                # Calculate session status
                status, status_color = self.calibration.calculate_session_status(darks_info, bias_info, flats_info)

                # Apply filters
                status_filter = self.session_status_filter.currentText()
                if status_filter != 'All' and status != status_filter:
                    continue

                if self.missing_only_checkbox.isChecked() and status != 'Missing':
                    continue

                # Update statistics
                total_count += 1
                if status == 'Complete':
                    complete_count += 1
                elif status == 'Partial':
                    partial_count += 1
                elif status == 'Missing':
                    missing_count += 1

                # Create session tree item
                session_name = f"{date} - {obj} - {filt or 'No Filter'}"
                session_item = QTreeWidgetItem(self.sessions_tree)
                session_item.setText(0, session_name)
                session_item.setText(1, status)
                session_item.setText(2, f"{frame_count} frames")

                # Quality metrics
                session_item.setText(3, f"{avg_fwhm:.2f}" if avg_fwhm is not None else 'N/A')
                session_item.setText(4, f"{avg_snr:.1f}" if avg_snr is not None else 'N/A')
                session_item.setText(5, f"{approved_count}/{frame_count}" if approved_count else '0/{}'.format(frame_count))

                # Calibration info
                session_item.setText(6, darks_info['display'])
                session_item.setText(7, bias_info['display'])
                session_item.setText(8, flats_info['display'])

                # Set status color (only for non-complete sessions)
                if status != 'Complete':
                    for col in range(9):
                        session_item.setForeground(col, status_color)

                # Store session data for details view
                session_item.setData(0, Qt.ItemDataRole.UserRole, {
                    'date': date,
                    'object': obj,
                    'filter': filt,
                    'frame_count': frame_count,
                    'avg_exposure': avg_exp,
                    'avg_temp': avg_temp,
                    'xbinning': xbin,
                    'ybinning': ybin,
                    'avg_fwhm': avg_fwhm,
                    'avg_snr': avg_snr,
                    'approved_count': approved_count,
                    'rejected_count': rejected_count,
                    'darks': darks_info,
                    'bias': bias_info,
                    'flats': flats_info,
                    'status': status
                })

            # Update statistics panel
            self.update_session_statistics(total_count, complete_count, partial_count, missing_count)

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to build sessions tree: {e}')

    def on_session_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle session tree item click."""
        session_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not session_data:
            return

        # Display session details
        details = []
        details.append(f"<h3>Session: {session_data['date']} - {session_data['object']}</h3>")
        details.append(f"<b>Filter:</b> {session_data['filter'] or 'None'}<br>")
        details.append(f"<b>Light Frames:</b> {session_data['frame_count']}<br>")

        # Handle None values for numeric fields
        avg_exp = session_data['avg_exposure']
        details.append(f"<b>Average Exposure:</b> {avg_exp:.1f}s<br>" if avg_exp is not None else "<b>Average Exposure:</b> N/A<br>")

        avg_temp = session_data['avg_temp']
        details.append(f"<b>Average Temperature:</b> {avg_temp:.1f}°C<br>" if avg_temp is not None else "<b>Average Temperature:</b> N/A<br>")

        details.append(f"<b>Binning:</b> {session_data['xbinning']}x{session_data['ybinning']}<br>")
        details.append(f"<b>Status:</b> {session_data['status']}<br>")

        # Quality metrics
        details.append("<h4>Quality Metrics:</h4>")
        avg_fwhm = session_data.get('avg_fwhm')
        details.append(f"<b>Average FWHM:</b> {avg_fwhm:.2f} arcsec<br>" if avg_fwhm is not None else "<b>Average FWHM:</b> N/A<br>")

        avg_snr = session_data.get('avg_snr')
        details.append(f"<b>Average SNR:</b> {avg_snr:.1f}<br>" if avg_snr is not None else "<b>Average SNR:</b> N/A<br>")

        approved_count = session_data.get('approved_count', 0)
        rejected_count = session_data.get('rejected_count', 0)
        not_graded_count = session_data['frame_count'] - approved_count - rejected_count
        approval_pct = (approved_count / session_data['frame_count'] * 100) if session_data['frame_count'] > 0 else 0
        details.append(f"<b>Approval:</b> {approved_count} approved ({approval_pct:.0f}%), {rejected_count} rejected, {not_graded_count} not graded<br>")

        details.append("<h4>Calibration Frames:</h4>")

        darks = session_data['darks']
        dark_exp = darks['exposure']
        details.append(f"<b>Darks ({dark_exp:.1f}s):</b> {darks['count']} frames" if dark_exp is not None else f"<b>Darks:</b> {darks['count']} frames")
        if darks['master_count'] > 0:
            details.append(f" + {darks['master_count']} master(s)")
        dark_quality = darks['quality']
        details.append(f" (Quality: {dark_quality:.0f}%)<br>" if dark_quality is not None else " (Quality: N/A)<br>")

        bias = session_data['bias']
        details.append(f"<b>Bias:</b> {bias['count']} frames")
        if bias['master_count'] > 0:
            details.append(f" + {bias['master_count']} master(s)")
        bias_quality = bias['quality']
        details.append(f" (Quality: {bias_quality:.0f}%)<br>" if bias_quality is not None else " (Quality: N/A)<br>")

        flats = session_data['flats']
        details.append(f"<b>Flats ({flats['filter'] or 'No Filter'}):</b> {flats['count']} frames")
        if flats['master_count'] > 0:
            details.append(f" + {flats['master_count']} master(s)")
        flat_quality = flats['quality']
        details.append(f" (Quality: {flat_quality:.0f}%)<br>" if flat_quality is not None else " (Quality: N/A)<br>")

        self.session_details_text.setHtml(''.join(details))

        # Generate recommendations
        recommendations = self.calibration.generate_recommendations(session_data)
        self.recommendations_text.setPlainText(recommendations)

    def update_session_statistics(self, total: int, complete: int, partial: int, missing: int) -> None:
        """Update the session statistics panel."""
        self.total_sessions_label.setText(f'Total Sessions: {total}')
        self.complete_sessions_label.setText(f'Complete: {complete}')
        self.partial_sessions_label.setText(f'Partial: {partial}')
        self.missing_sessions_label.setText(f'Missing: {missing}')

        if total > 0:
            completion_rate = (complete / total) * 100
            self.completion_rate_label.setText(f'Completion Rate: {completion_rate:.1f}%')
        else:
            self.completion_rate_label.setText('Completion Rate: 0%')

    def export_session_report(self) -> None:
        """Export session report to text file."""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                'Export Session Report',
                'session_report.txt',
                'Text Files (*.txt);;All Files (*)'
            )

            if not filename:
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all sessions
            cursor.execute('''
                SELECT
                    date_loc,
                    object,
                    filter,
                    COUNT(*) as frame_count,
                    AVG(exposure) as avg_exposure,
                    AVG(ccd_temp) as avg_temp,
                    xbinning,
                    ybinning
                FROM xisf_files
                WHERE imagetyp LIKE '%Light%'
                    AND date_loc IS NOT NULL
                    AND object IS NOT NULL
                GROUP BY date_loc, object, filter
                ORDER BY date_loc DESC, object, filter
            ''')

            sessions = cursor.fetchall()

            with open(filename, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("XISF FILE MANAGER - SESSION CALIBRATION REPORT\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Sessions: {len(sessions)}\n\n")

                complete_count = 0
                partial_count = 0
                missing_count = 0

                for session_data in sessions:
                    date, obj, filt, frame_count, avg_exp, avg_temp, xbin, ybin = session_data

                    # Find matching calibration frames
                    darks_info = self.calibration.find_matching_darks(avg_exp, avg_temp, xbin, ybin)
                    bias_info = self.calibration.find_matching_bias(avg_temp, xbin, ybin)
                    flats_info = self.calibration.find_matching_flats(filt, avg_temp, xbin, ybin, date)

                    status, _ = self.calibration.calculate_session_status(darks_info, bias_info, flats_info)

                    if status == 'Complete':
                        complete_count += 1
                    elif status == 'Partial':
                        partial_count += 1
                    else:
                        missing_count += 1

                    f.write("-" * 80 + "\n")
                    f.write(f"Session: {date} - {obj} - {filt or 'No Filter'}\n")
                    f.write(f"Status: {status}\n")
                    f.write(f"Light Frames: {frame_count} | Exposure: {avg_exp:.1f}s | Temp: {avg_temp:.1f}°C | Binning: {xbin}x{ybin}\n\n")

                    f.write(f"  Darks ({avg_exp:.1f}s): {darks_info['count']} frames")
                    if darks_info['master_count'] > 0:
                        f.write(f" + {darks_info['master_count']} master(s)")
                    f.write(f" (Quality: {darks_info['quality']:.0f}%)\n")

                    f.write(f"  Bias: {bias_info['count']} frames")
                    if bias_info['master_count'] > 0:
                        f.write(f" + {bias_info['master_count']} master(s)")
                    f.write(f" (Quality: {bias_info['quality']:.0f}%)\n")

                    f.write(f"  Flats ({filt or 'No Filter'}): {flats_info['count']} frames")
                    if flats_info['master_count'] > 0:
                        f.write(f" + {flats_info['master_count']} master(s)")
                    f.write(f" (Quality: {flats_info['quality']:.0f}%)\n")

                    # Add recommendations if needed
                    session_dict = {
                        'avg_exposure': avg_exp,
                        'avg_temp': avg_temp,
                        'xbinning': xbin,
                        'ybinning': ybin,
                        'filter': filt,
                        'darks': darks_info,
                        'bias': bias_info,
                        'flats': flats_info
                    }
                    recommendations = self.calibration.generate_recommendations(session_dict)
                    if recommendations and not recommendations.startswith('✓ All'):
                        f.write(f"\n  Recommendations:\n")
                        for line in recommendations.split('\n'):
                            if line.strip():
                                f.write(f"    {line}\n")

                    f.write("\n")

                # Summary
                f.write("=" * 80 + "\n")
                f.write("SUMMARY\n")
                f.write("=" * 80 + "\n")
                f.write(f"Complete Sessions: {complete_count}\n")
                f.write(f"Partial Sessions: {partial_count}\n")
                f.write(f"Missing Calibration: {missing_count}\n")
                if len(sessions) > 0:
                    completion_rate = (complete_count / len(sessions)) * 100
                    f.write(f"Completion Rate: {completion_rate:.1f}%\n")

            conn.close()

            QMessageBox.information(
                self, 'Export Complete',
                f'Session report exported to:\n{filename}'
            )

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export report: {e}')

    def save_splitter_state(self) -> None:
        """Save the splitter sizes to settings."""
        sizes = self.details_splitter.sizes()
        self.settings.setValue('sessions_details_splitter_sizes', sizes)

    def restore_splitter_state(self) -> None:
        """Restore the splitter sizes from settings."""
        saved_sizes = self.settings.value('sessions_details_splitter_sizes')
        if saved_sizes:
            # Convert to integers (QSettings may return strings)
            sizes = [int(s) for s in saved_sizes]
            self.details_splitter.setSizes(sizes)
