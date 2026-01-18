#!/usr/bin/env python3
"""
Configuration Manager for AstroFileManager

This module provides a JSON-based configuration storage system as a replacement
for Qt's QSettings (which uses the Windows registry on Windows).

The configuration file is stored in a user-specific location:
- Windows: C:\\Users\\<username>\\AppData\\Local\\AstroFileManager\\config.json
- Linux: ~/.config/AstroFileManager/config.json
- macOS: ~/Library/Application Support/AstroFileManager/config.json

This allows multiple versions of the application to maintain separate settings
by using different configuration file names or directories.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional, Union
from PyQt6.QtCore import QByteArray


class ConfigManager:
    """
    Manages application configuration using a JSON file.

    This class provides a QSettings-compatible interface for storing and
    retrieving application settings, but uses a JSON file instead of the
    Windows registry.

    Attributes:
        config_file (Path): Path to the JSON configuration file
        _config (dict): In-memory configuration dictionary
    """

    def __init__(self, organization: str = "AstroFileManager",
                 application: str = "AstroFileManager",
                 config_filename: str = "config.json"):
        """
        Initialize the configuration manager.

        Args:
            organization: Organization name (used for directory structure)
            application: Application name (used for directory structure)
            config_filename: Name of the configuration file (default: config.json)

        Example:
            # Default configuration
            config = ConfigManager()

            # Custom configuration for a different version
            config = ConfigManager(config_filename="config_v2.json")
        """
        self.organization = organization
        self.application = application

        # Determine the configuration directory based on the platform
        self.config_dir = self._get_config_directory()
        self.config_file = self.config_dir / config_filename

        # Create the configuration directory if it doesn't exist
        self._ensure_config_directory()

        # Load existing configuration or create empty one
        self._config = self._load_config()

    def _get_config_directory(self) -> Path:
        """
        Get the platform-specific configuration directory.

        Returns:
            Path object pointing to the configuration directory

        Platform-specific locations:
            Windows: C:\\Users\\<username>\\AppData\\Local\\AstroFileManager
            Linux: ~/.config/AstroFileManager
            macOS: ~/Library/Application Support/AstroFileManager
        """
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('LOCALAPPDATA',
                                          Path.home() / 'AppData' / 'Local'))
        elif os.name == 'posix':
            if 'darwin' in os.sys.platform:  # macOS
                base_dir = Path.home() / 'Library' / 'Application Support'
            else:  # Linux and other Unix-like systems
                base_dir = Path(os.environ.get('XDG_CONFIG_HOME',
                                              Path.home() / '.config'))
        else:
            # Fallback for unknown platforms
            base_dir = Path.home() / '.config'

        return base_dir / self.organization

    def _ensure_config_directory(self) -> None:
        """
        Create the configuration directory if it doesn't exist.

        This method creates all parent directories as needed.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Warning: Could not create config directory {self.config_dir}: {e}")

    def _load_config(self) -> dict:
        """
        Load configuration from the JSON file.

        Returns:
            Dictionary containing the configuration data, or empty dict if
            the file doesn't exist or cannot be read.
        """
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load config from {self.config_file}: {e}")
            return {}

    def _save_config(self) -> None:
        """
        Save the current configuration to the JSON file.

        The configuration is saved with indentation for readability.
        If the save fails, a warning is printed but the application continues.
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"Warning: Could not save config to {self.config_file}: {e}")

    def setValue(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        This method is compatible with QSettings.setValue().
        The configuration is automatically saved to disk after setting the value.

        Args:
            key: Configuration key (e.g., 'repository_path', 'catalog_tree_col_0')
            value: Value to store (must be JSON-serializable)

        Example:
            config.setValue('repository_path', '/path/to/repo')
            config.setValue('catalog_tree_col_0', 150)
        """
        # Convert QByteArray to base64 string for JSON serialization
        if isinstance(value, QByteArray):
            value = value.toBase64().data().decode('utf-8')

        self._config[key] = value
        self._save_config()

    def value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        This method is compatible with QSettings.value().

        Args:
            key: Configuration key to retrieve
            default: Default value if the key doesn't exist

        Returns:
            The stored value, or the default if the key is not found

        Example:
            path = config.value('repository_path', '')
            width = config.value('catalog_tree_col_0', 100)
        """
        value = self._config.get(key, default)

        # Convert base64 string back to QByteArray if needed
        # (for geometry data stored by Qt)
        if isinstance(value, str) and key == 'geometry':
            try:
                byte_array = QByteArray.fromBase64(value.encode('utf-8'))
                return byte_array
            except Exception:
                return default

        return value

    def remove(self, key: str) -> None:
        """
        Remove a configuration key.

        This method is compatible with QSettings.remove().

        Args:
            key: Configuration key to remove

        Example:
            config.remove('obsolete_setting')
        """
        if key in self._config:
            del self._config[key]
            self._save_config()

    def contains(self, key: str) -> bool:
        """
        Check if a configuration key exists.

        This method is compatible with QSettings.contains().

        Args:
            key: Configuration key to check

        Returns:
            True if the key exists, False otherwise

        Example:
            if config.contains('repository_path'):
                path = config.value('repository_path')
        """
        return key in self._config

    def clear(self) -> None:
        """
        Clear all configuration data.

        This method is compatible with QSettings.clear().
        Use with caution as it removes all stored settings.

        Example:
            config.clear()  # Remove all settings
        """
        self._config = {}
        self._save_config()

    def allKeys(self) -> list:
        """
        Get all configuration keys.

        This method is compatible with QSettings.allKeys().

        Returns:
            List of all configuration keys

        Example:
            for key in config.allKeys():
                print(f"{key}: {config.value(key)}")
        """
        return list(self._config.keys())

    def sync(self) -> None:
        """
        Sync configuration to disk.

        This method is compatible with QSettings.sync().
        In this implementation, changes are automatically saved,
        so this method is a no-op but is provided for compatibility.

        Example:
            config.sync()  # Ensure all changes are written to disk
        """
        self._save_config()

    def get_config_file_path(self) -> str:
        """
        Get the full path to the configuration file.

        This is useful for debugging or displaying to the user where
        their settings are stored.

        Returns:
            String path to the configuration file

        Example:
            print(f"Configuration stored at: {config.get_config_file_path()}")
        """
        return str(self.config_file)

    def migrate_from_qsettings(self, qsettings) -> int:
        """
        Migrate settings from a QSettings object to this ConfigManager.

        This is a helper method to facilitate migration from the registry-based
        QSettings to the JSON-based ConfigManager.

        Args:
            qsettings: A QSettings object to migrate from

        Returns:
            Number of settings migrated

        Example:
            from PyQt6.QtCore import QSettings
            old_settings = QSettings('AstroFileManager', 'AstroFileManager')
            config = ConfigManager()
            count = config.migrate_from_qsettings(old_settings)
            print(f"Migrated {count} settings")
        """
        keys = qsettings.allKeys()
        migrated = 0

        for key in keys:
            value = qsettings.value(key)
            if value is not None:
                self.setValue(key, value)
                migrated += 1

        return migrated

    def get_backup_directory(self) -> str:
        """
        Get the database backup directory path.

        Returns the configured backup directory, or creates a default one
        in the application's config directory if not set.

        Returns:
            String path to the backup directory

        Example:
            backup_dir = config.get_backup_directory()
        """
        # Check if backup directory is configured
        backup_dir = self.value('backup_directory', '')

        # If not configured, use default location in config directory
        if not backup_dir:
            backup_dir = str(self.config_dir / 'database_backups')
            self.setValue('backup_directory', backup_dir)

        return backup_dir
