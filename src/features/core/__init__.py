"""
Core Features Package

Contains fundamental team-level features:
- ELO ratings (team strength)
- Recent form (last 5-10 games performance)
- Team statistics (attack/defence strength, goals)

These features are calculated per team and represent their
current playing ability and form.

Usage:
    from src.features.core import ELOCalculator, FormCalculator, TeamStatisticsCalculator
    
    elo = ELOCalculator()
    form = FormCalculator()
    stats = TeamStatisticsCalculator()
"""

from .elo_calculator import ELOCalculator
from .form_calculator import FormCalculator
from .team_features import TeamFeatures
from .team_statistics import TeamStatisticsCalculator

__all__ = [
    'ELOCalculator',
    'FormCalculator',
    'TeamFeatures',
    'TeamStatisticsCalculator',
]