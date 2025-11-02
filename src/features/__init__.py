"""
Features Package

Provides feature calculation for betting models.
"""

from .feature_engine import FeatureEngine

# Import subpackages for direct access if needed
from .core import team_strength, recent_form, team_statistics
from .match_context import importance, rivalry, head_to_head

__all__ = [
    'FeatureEngine',
    'team_strength',
    'recent_form',
    'team_statistics',
    'importance',
    'rivalry',
    'head_to_head'
]

# Version
__version__ = '1.0.0'