"""
Core business logic for AstroFileManager.

This package contains the core business logic separated from UI concerns:
- database: Database operations and queries
- calibration: Calibration frame matching logic
- project_manager: Project-based workflow management
- project_templates: Pre-configured project templates
"""

from .database import DatabaseManager
from .calibration import CalibrationMatcher
from .project_manager import ProjectManager, Project, FilterGoalProgress
from .project_templates import (
    ProjectTemplate, FilterGoal, get_templates,
    get_template_by_name, create_filter_goals_dict,
    NARROWBAND_TEMPLATE, BROADBAND_TEMPLATE, CUSTOM_TEMPLATE
)

__all__ = [
    'DatabaseManager', 'CalibrationMatcher',
    'ProjectManager', 'Project', 'FilterGoalProgress',
    'ProjectTemplate', 'FilterGoal', 'get_templates',
    'get_template_by_name', 'create_filter_goals_dict',
    'NARROWBAND_TEMPLATE', 'BROADBAND_TEMPLATE', 'CUSTOM_TEMPLATE'
]
