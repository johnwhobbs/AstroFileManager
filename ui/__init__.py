"""
UI components for AstroFileManager.

This package contains tab-specific UI classes for the main application.
Each tab is implemented as a separate class to improve modularity.
"""

from .import_tab import ImportTab
from .settings_tab import SettingsTab
from .maintenance_tab import MaintenanceTab
from .sessions_tab import SessionsTab

__all__ = [
    'ImportTab',
    'SettingsTab',
    'MaintenanceTab',
    'SessionsTab'
]

# Future tab classes will be added here:
# from .view_tab import ViewTab
# from .analytics_tab import AnalyticsTab
