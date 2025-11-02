"""
Match Context Package

Features that describe the context and circumstances of a match.

Why context matters:
- Derbies are unpredictable (form doesn't matter)
- High-stakes matches are more defensive
- Teams fighting relegation play differently
- Season timing affects tactics and motivation

Modules:
    - importance: Match importance score (title race, survival, etc.)
    - rivalry: Derby detection and rivalry factors
    - head_to_head: Historical matchups between teams
    - season_timing: Fixture congestion, season stage
"""

from .importance import MatchImportanceCalculator
from .rivalry import RivalryDetector
from .head_to_head import HeadToHeadAnalyser
from .season_timing import SeasonTimingAnalyser

__all__ = [
    'MatchImportanceCalculator',
    'RivalryDetector',
    'HeadToHeadAnalyser',
    'SeasonTimingAnalyser'
]