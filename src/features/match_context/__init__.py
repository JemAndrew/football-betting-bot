"""
Match Context Features Package

Contains match-specific contextual features:
- Head-to-head history (H2H record between teams)
- Match importance (league position stakes)
- Rivalry detection (derby matches, historic rivalries)
- Season timing (early/mid/late season, fixture congestion)

These features provide context about the specific matchup
beyond just the teams' current form and strength.

Usage:
    from src.features.match_context import (
        HeadToHeadAnalyser,
        ImportanceCalculator,
        RivalryDetector,
        SeasonTimingAnalyser
    )
    
    h2h = HeadToHeadAnalyser()
    importance = ImportanceCalculator()
    rivalry = RivalryDetector()
    timing = SeasonTimingAnalyser()
"""

from .head_to_head import HeadToHeadAnalyser
from .importance import MatchImportanceCalculator
from .rivalry import RivalryDetector
from .season_timing import SeasonTimingAnalyser

__all__ = [
    'HeadToHeadAnalyser',
    'ImportanceCalculator',
    'RivalryDetector',
    'SeasonTimingAnalyser',
]