"""
Goals Models Package

Contains all goal-related prediction models:
- BTTS (Both Teams To Score)
- Over/Under goals
- Clean Sheets
- Poisson Goals (if we have it)

Usage:
    from src.models.goals import BTTSModel, OverUnderModel, CleanSheetModel
    
    btts = BTTSModel()
    ou = OverUnderModel(goal_threshold=2.5)
    cs = CleanSheetModel()
"""

# Import models for easy access
try:
    from .btts import BTTSModel
    from .over_under import OverUnderModel
    from .clean_sheets import CleanSheetModel
    
    # Try to import Poisson model if it exists
    try:
        from .poisson_goals import PoissonGoalsModel
        __all__ = ['BTTSModel', 'OverUnderModel', 'CleanSheetModel', 'PoissonGoalsModel']
    except ImportError:
        __all__ = ['BTTSModel', 'OverUnderModel', 'CleanSheetModel']

except ImportError as e:
    # If imports fail, at least define __all__ so package can be imported
    __all__ = []
    import warnings
    warnings.warn(f"Could not import all goals models: {e}")