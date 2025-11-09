"""
Core business logic for AstroFileManager.

This package contains the core business logic separated from UI concerns:
- database: Database operations and queries
- calibration: Calibration frame matching logic
"""

from .database import DatabaseManager
from .calibration import CalibrationMatcher

__all__ = ['DatabaseManager', 'CalibrationMatcher']
