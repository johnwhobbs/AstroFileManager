"""
Project Templates for AstroFileManager

Provides pre-configured project templates for common imaging workflows.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FilterGoal:
    """Represents a target frame count for a specific filter."""
    filter: str
    target_count: int


@dataclass
class ProjectTemplate:
    """Represents a project template with predefined filter goals."""
    name: str
    description: str
    filter_goals: List[FilterGoal]


# Pre-defined templates
NARROWBAND_TEMPLATE = ProjectTemplate(
    name="Narrowband (SHO)",
    description="Standard narrowband imaging: 90 frames each of Ha, OIII, SII",
    filter_goals=[
        FilterGoal("Ha", 90),
        FilterGoal("OIII", 90),
        FilterGoal("SII", 90),
    ]
)

BROADBAND_TEMPLATE = ProjectTemplate(
    name="Broadband (LRGB)",
    description="Broadband LRGB imaging: 270 Luminance, 270 each RGB",
    filter_goals=[
        FilterGoal("L", 270),
        FilterGoal("R", 270),
        FilterGoal("G", 270),
        FilterGoal("B", 270),
    ]
)

CUSTOM_TEMPLATE = ProjectTemplate(
    name="Custom",
    description="Define your own filter goals",
    filter_goals=[]
)


def get_templates() -> List[ProjectTemplate]:
    """
    Get list of available project templates.

    Returns:
        List of ProjectTemplate objects
    """
    return [
        NARROWBAND_TEMPLATE,
        BROADBAND_TEMPLATE,
        CUSTOM_TEMPLATE,
    ]


def get_template_by_name(name: str) -> ProjectTemplate:
    """
    Get a template by name.

    Args:
        name: Template name

    Returns:
        ProjectTemplate object

    Raises:
        ValueError: If template not found
    """
    for template in get_templates():
        if template.name == name:
            return template
    raise ValueError(f"Template not found: {name}")


def create_filter_goals_dict(template: ProjectTemplate) -> Dict[str, int]:
    """
    Convert template filter goals to dictionary format.

    Args:
        template: ProjectTemplate object

    Returns:
        Dictionary mapping filter names to target counts
    """
    return {goal.filter: goal.target_count for goal in template.filter_goals}
