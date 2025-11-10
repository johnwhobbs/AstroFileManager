"""
UI components for AstroFileManager.

This package contains tab-specific UI classes for the main application.
Each tab is implemented as a separate class to improve modularity.
"""

from .import_tab import ImportTab
from .settings_tab import SettingsTab
from .maintenance_tab import MaintenanceTab
from .sessions_tab import SessionsTab
from .analytics_tab import AnalyticsTab
from .view_catalog_tab import ViewCatalogTab

__all__ = [
    'ImportTab',
    'SettingsTab',
    'MaintenanceTab',
    'SessionsTab',
    'AnalyticsTab',
    'ViewCatalogTab'
]
