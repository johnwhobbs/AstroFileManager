"""
Settings tab UI for AstroFileManager.

This module contains the SettingsTab class which handles application settings
including repository location, timezone, and theme preferences.
"""

import os
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QMessageBox, QLabel, QLineEdit, QGroupBox, QComboBox,
    QRadioButton, QButtonGroup
)

from core.config_manager import ConfigManager


class SettingsTab(QWidget):
    """Settings tab for application configuration."""

    def __init__(self, settings: ConfigManager) -> None:
        """
        Initialize Settings tab.

        Args:
            settings: ConfigManager instance for app settings
        """
        super().__init__()
        self.settings = settings

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Image Repository Location
        repo_group = QGroupBox("Image Repository")
        repo_layout = QVBoxLayout()

        repo_info = QLabel("Set the location for your organized XISF files:")
        repo_layout.addWidget(repo_info)

        repo_path_layout = QHBoxLayout()
        repo_path_label = QLabel("Repository Path:")
        repo_path_label.setMinimumWidth(120)
        self.repo_path_input = QLineEdit()
        self.repo_path_input.setReadOnly(True)
        current_repo = self.settings.value('repository_path', '')
        if current_repo:
            # Standardize on forward slashes
            current_repo = current_repo.replace('\\', '/')
        self.repo_path_input.setText(current_repo)

        browse_repo_btn = QPushButton('Browse...')
        browse_repo_btn.clicked.connect(self.browse_repository)

        repo_path_layout.addWidget(repo_path_label)
        repo_path_layout.addWidget(self.repo_path_input)
        repo_path_layout.addWidget(browse_repo_btn)
        repo_layout.addLayout(repo_path_layout)

        repo_group.setLayout(repo_layout)
        layout.addWidget(repo_group)

        # Timezone settings group
        timezone_group = QGroupBox("Timezone")
        timezone_layout = QVBoxLayout()

        timezone_info = QLabel("Set your local timezone for DATE-OBS conversion:")
        timezone_layout.addWidget(timezone_info)

        timezone_help = QLabel("Used to convert UTC timestamps (DATE-OBS) to local time for session grouping.")
        timezone_help.setStyleSheet("color: #888888; font-size: 10px;")
        timezone_layout.addWidget(timezone_help)

        timezone_selector_layout = QHBoxLayout()
        timezone_label = QLabel("Timezone:")
        timezone_label.setMinimumWidth(120)
        self.timezone_combo = QComboBox()

        # Common timezones
        common_timezones = [
            'UTC',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'America/Phoenix',
            'America/Anchorage',
            'Pacific/Honolulu',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Europe/Rome',
            'Europe/Madrid',
            'Europe/Athens',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Hong_Kong',
            'Asia/Singapore',
            'Asia/Dubai',
            'Australia/Sydney',
            'Australia/Melbourne',
            'Australia/Perth',
            'Pacific/Auckland'
        ]

        self.timezone_combo.addItems(common_timezones)

        # Set current timezone
        current_timezone = self.settings.value('timezone', 'UTC')
        index = self.timezone_combo.findText(current_timezone)
        if index >= 0:
            self.timezone_combo.setCurrentIndex(index)

        save_timezone_btn = QPushButton('Save Timezone')
        save_timezone_btn.clicked.connect(self.save_timezone_setting)

        timezone_selector_layout.addWidget(timezone_label)
        timezone_selector_layout.addWidget(self.timezone_combo)
        timezone_selector_layout.addWidget(save_timezone_btn)
        timezone_layout.addLayout(timezone_selector_layout)

        timezone_group.setLayout(timezone_layout)
        layout.addWidget(timezone_group)

        # Theme settings group
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout()

        # Radio buttons for theme selection
        self.theme_button_group = QButtonGroup()
        self.standard_theme_radio = QRadioButton("Standard Theme")
        self.dark_theme_radio = QRadioButton("Dark Theme")

        self.theme_button_group.addButton(self.standard_theme_radio, 0)
        self.theme_button_group.addButton(self.dark_theme_radio, 1)

        theme_layout.addWidget(self.standard_theme_radio)
        theme_layout.addWidget(self.dark_theme_radio)

        # Set current theme
        current_theme = self.settings.value('theme', 'standard')
        if current_theme == 'standard':
            self.standard_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)

        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Update settings group
        update_group = QGroupBox("Updates")
        update_layout = QVBoxLayout()

        update_info = QLabel("Configure automatic update preferences:")
        update_layout.addWidget(update_info)

        # Radio buttons for update branch selection
        self.update_button_group = QButtonGroup()
        self.main_branch_radio = QRadioButton("Main Branch (Stable)")
        self.main_branch_radio.setToolTip("Production-ready stable releases")
        self.dev_branch_radio = QRadioButton("Development Branch (Latest features)")
        self.dev_branch_radio.setToolTip("Latest features, may be less stable")

        self.update_button_group.addButton(self.main_branch_radio, 0)
        self.update_button_group.addButton(self.dev_branch_radio, 1)

        update_layout.addWidget(self.main_branch_radio)
        update_layout.addWidget(self.dev_branch_radio)

        # Set current update branch preference
        current_branch = self.settings.value('update_branch', 'main')
        if current_branch == 'main':
            self.main_branch_radio.setChecked(True)
        else:
            self.dev_branch_radio.setChecked(True)

        # Save button for update preferences
        update_button_layout = QHBoxLayout()
        update_button_layout.addStretch()
        save_update_btn = QPushButton('Save Update Preferences')
        save_update_btn.clicked.connect(self.save_update_preferences)
        update_button_layout.addWidget(save_update_btn)
        update_layout.addLayout(update_button_layout)

        update_group.setLayout(update_layout)
        layout.addWidget(update_group)

        # OK button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton('Apply Theme')
        ok_button.clicked.connect(self.apply_theme_setting)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)

        # Add stretch to push everything to the top
        layout.addStretch()

    def browse_repository(self) -> None:
        """Browse for repository location."""
        current_path = self.repo_path_input.text()
        directory = QFileDialog.getExistingDirectory(
            self, 'Select Image Repository Location',
            current_path if current_path else ''
        )

        if directory:
            # Normalize path to use OS-specific separators
            directory = os.path.normpath(directory)
            self.repo_path_input.setText(directory)
            self.settings.setValue('repository_path', directory)
            QMessageBox.information(
                self, 'Repository Path Updated',
                f'Image repository location set to:\n{directory}'
            )

    def save_timezone_setting(self) -> None:
        """Save the selected timezone."""
        timezone = self.timezone_combo.currentText()
        self.settings.setValue('timezone', timezone)
        QMessageBox.information(
            self,
            'Timezone Saved',
            f'Timezone set to: {timezone}\n\nThis will be used for converting DATE-OBS timestamps.'
        )

    def save_update_preferences(self) -> None:
        """Save the update branch preference."""
        if self.main_branch_radio.isChecked():
            branch = 'main'
        else:
            branch = 'development'

        # Save update branch preference
        self.settings.setValue('update_branch', branch)

        # Show confirmation message
        QMessageBox.information(
            self,
            'Update Preferences Saved',
            f'Update branch preference set to: {branch}\n\n'
            f'This will be used when checking for updates from the Help menu.'
        )

    def apply_theme_setting(self) -> None:
        """Apply the selected theme."""
        if self.standard_theme_radio.isChecked():
            theme = 'standard'
        else:
            theme = 'dark'

        # Save theme preference
        self.settings.setValue('theme', theme)

        # Show message that restart is needed
        QMessageBox.information(
            self,
            'Theme Changed',
            'Theme has been changed. Please restart the application for the changes to take effect.'
        )
