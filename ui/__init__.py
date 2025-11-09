"""
UI components for AstroFileManager.

This package contains tab-specific UI classes for the main application.
Each tab is implemented as a separate class to improve modularity.
"""

from .import_tab import ImportTab
from .view_tab import ViewTab
from .sessions_tab import SessionsTab
from .analytics_tab import AnalyticsTab
from .maintenance_tab import MaintenanceTab
from .settings_tab import SettingsTab

__all__ = [
    'ImportTab',
    'ViewTab',
    'SessionsTab',
    'AnalyticsTab',
    'MaintenanceTab',
    'SettingsTab'
]
