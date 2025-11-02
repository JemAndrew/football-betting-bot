"""
Models Package

Contains all betting prediction models.

Architecture:
    base_model.py         → Base class for all models
    model_factory.py      → Orchestrates all models
    model_trainer.py      → Training utilities (optional)
    ensemble.py           → Combines multiple models (advanced)
    
    goals/                → Goal-related predictions
    ├── btts.py          → Both Teams To Score
    ├── over_under.py    → Over/Under goals
    ├── clean_sheets.py  → Clean sheet probability
    └── poisson_goals.py → Poisson distribution model

Usage:
    # Simple way - use ModelFactory
    from src.models import ModelFactory
    
    factory = ModelFactory()
    predictions = factory.predict_all(home_id=1, away_id=2, date='2024-01-15')
    
    # Or import individual models
    from src.models.goals import BTTSModel, OverUnderModel
    
    btts = BTTSModel()
    prediction = btts.predict(1, 2, '2024-01-15')
"""

# Core model infrastructure
try:
    from .base_model import BaseModel
    from .model_factory import ModelFactory
    
    __all__ = ['BaseModel', 'ModelFactory']
    
except ImportError as e:
    # If imports fail during setup, define empty exports
    __all__ = []
    import warnings
    warnings.warn(f"Could not import model infrastructure: {e}")

# Try to import goals models
try:
    from .goals import BTTSModel, OverUnderModel, CleanSheetModel
    __all__.extend(['BTTSModel', 'OverUnderModel', 'CleanSheetModel'])
except ImportError:
    pass

# Optional imports (don't fail if not available yet)
try:
    from .model_trainer import ModelTrainer
    __all__.append('ModelTrainer')
except ImportError:
    pass

try:
    from .ensemble import EnsembleModel
    __all__.append('EnsembleModel')
except ImportError:
    pass