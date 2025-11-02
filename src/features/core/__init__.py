"""
Core Features Package

Essential features that are always enabled.
These are the foundation of match prediction.

Modules:
    - team_strength: ELO ratings and power metrics
    - recent_form: Last 5-10 games performance
    - team_statistics: Attack/defence stats, goals, clean sheets
"""

from .team_strength import TeamStrengthCalculator
from .recent_form import RecentFormCalculator
from .team_statistics import TeamStatisticsCalculator

__all__ = [
    'TeamStrengthCalculator',
    'RecentFormCalculator',
    'TeamStatisticsCalculator'
]