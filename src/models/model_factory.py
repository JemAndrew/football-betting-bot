"""
Model Factory - One Place to Rule Them All

This is the master orchestrator for all betting models.
Instead of importing 5 different models, just use ModelFactory.

Why we need this:
- Single import for all models
- Consistent interface - one predict() call gets everything
- Easy to add/remove models without changing code everywhere
- Centralised model management and configuration

Usage:
    factory = ModelFactory()
    
    # Get all predictions for a match
    predictions = factory.predict_all(
        home_id=1,
        away_id=2,
        date='2024-01-15'
    )
    
    # Returns complete dict with all market predictions:
    {
        'goals': {...},           # Poisson goals model
        'btts': {...},            # BTTS model
        'over_under': {...},      # O/U 2.5 model
        'clean_sheets': {...},    # Clean sheet model
        'summary': {...}          # Quick summary
    }
    
    # Or get individual model predictions
    btts_prediction = factory.predict_btts(1, 2, '2024-01-15')
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

# Import all our models
# NOTE: You need to adjust these imports based on where you put the model files
try:
    # Try importing from goals package first
    from src.models.goals.btts import BTTSModel
    from src.models.goals.over_under import OverUnderModel
    from src.models.goals.clean_sheets import CleanSheetModel
except ImportError:
    # Fallback to direct imports (for testing)
    try:
        from btts import BTTSModel
        from over_under import OverUnderModel
        from clean_sheets import CleanSheetModel
    except ImportError:
        logger.warning("Could not import models - make sure they're in the right location")
        BTTSModel = None
        OverUnderModel = None
        CleanSheetModel = None

# Set up logging
logger = logging.getLogger(__name__)


class ModelFactory:
    """
    Factory for creating and managing all prediction models.
    
    This is your one-stop shop for getting predictions.
    All complexity hidden behind a simple interface.
    """
    
    def __init__(
        self,
        enable_btts: bool = True,
        enable_over_under: bool = True,
        enable_clean_sheets: bool = True,
        over_under_threshold: float = 2.5
    ):
        """
        Initialise model factory.
        
        Args:
            enable_btts: Whether to load BTTS model
            enable_over_under: Whether to load O/U model
            enable_clean_sheets: Whether to load clean sheet model
            over_under_threshold: Goal threshold for O/U model (2.5, 3.5, etc.)
        """
        self.models = {}
        self.enabled_models = []
        
        logger.info("Initialising Model Factory...")
        
        # Initialise BTTS model
        if enable_btts and BTTSModel:
            try:
                self.models['btts'] = BTTSModel()
                self.enabled_models.append('btts')
                logger.info("  ✅ BTTS model loaded")
            except Exception as e:
                logger.error(f"  ❌ Failed to load BTTS model: {e}")
        
        # Initialise Over/Under model
        if enable_over_under and OverUnderModel:
            try:
                self.models['over_under'] = OverUnderModel(
                    goal_threshold=over_under_threshold
                )
                self.enabled_models.append('over_under')
                logger.info(f"  ✅ Over/Under {over_under_threshold} model loaded")
            except Exception as e:
                logger.error(f"  ❌ Failed to load Over/Under model: {e}")
        
        # Initialise Clean Sheet model
        if enable_clean_sheets and CleanSheetModel:
            try:
                self.models['clean_sheets'] = CleanSheetModel()
                self.enabled_models.append('clean_sheets')
                logger.info("  ✅ Clean Sheets model loaded")
            except Exception as e:
                logger.error(f"  ❌ Failed to load Clean Sheets model: {e}")
        
        logger.info(f"Model Factory initialised with {len(self.models)} models")
        
        if not self.models:
            logger.warning(
                "⚠️  No models loaded! Check your imports and model files."
            )
    
    def predict_all(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        league_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get predictions from ALL enabled models.
        
        This is the main method you'll use - one call, all predictions.
        
        Args:
            home_team_id: Home team database ID
            away_team_id: Away team database ID
            match_date: Match date (YYYY-MM-DD format)
            league_name: Optional league name for league-specific adjustments
            
        Returns:
            Dictionary containing all model predictions plus summary:
            {
                'btts': {...},
                'over_under': {...},
                'clean_sheets': {...},
                'summary': {
                    'best_bet': 'Over 2.5',
                    'confidence': 0.85,
                    'expected_total_goals': 3.2
                },
                'match_info': {
                    'home_id': 1,
                    'away_id': 2,
                    'date': '2024-01-15'
                }
            }
        """
        logger.info(
            f"Getting predictions for match: {home_team_id} vs {away_team_id}"
        )
        
        predictions = {
            'match_info': {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'match_date': match_date,
                'league': league_name,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # Get BTTS prediction
        if 'btts' in self.models:
            try:
                btts_pred = self.models['btts'].predict(
                    home_team_id, away_team_id, match_date, league_name
                )
                predictions['btts'] = btts_pred
                logger.debug(f"  ✅ BTTS: {btts_pred['btts_yes_prob']:.1%}")
            except Exception as e:
                logger.error(f"  ❌ BTTS prediction failed: {e}")
                predictions['btts'] = {'error': str(e)}
        
        # Get Over/Under prediction
        if 'over_under' in self.models:
            try:
                ou_pred = self.models['over_under'].predict(
                    home_team_id, away_team_id, match_date
                )
                predictions['over_under'] = ou_pred
                logger.debug(f"  ✅ Over 2.5: {ou_pred['over_prob']:.1%}")
            except Exception as e:
                logger.error(f"  ❌ Over/Under prediction failed: {e}")
                predictions['over_under'] = {'error': str(e)}
        
        # Get Clean Sheets prediction
        if 'clean_sheets' in self.models:
            try:
                cs_pred = self.models['clean_sheets'].predict(
                    home_team_id, away_team_id, match_date
                )
                predictions['clean_sheets'] = cs_pred
                logger.debug(
                    f"  ✅ Clean Sheets - Home: {cs_pred['home_clean_sheet_prob']:.1%}, "
                    f"Away: {cs_pred['away_clean_sheet_prob']:.1%}"
                )
            except Exception as e:
                logger.error(f"  ❌ Clean Sheets prediction failed: {e}")
                predictions['clean_sheets'] = {'error': str(e)}
        
        # Create summary of all predictions
        predictions['summary'] = self._create_summary(predictions)
        
        logger.info(f"✅ All predictions complete")
        
        return predictions
    
    def predict_btts(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        league_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get just BTTS prediction.
        
        Convenience method if you only need BTTS.
        """
        if 'btts' not in self.models:
            return {'error': 'BTTS model not loaded'}
        
        return self.models['btts'].predict(
            home_team_id, away_team_id, match_date, league_name
        )
    
    def predict_over_under(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str
    ) -> Dict[str, Any]:
        """
        Get just Over/Under prediction.
        
        Convenience method if you only need O/U.
        """
        if 'over_under' not in self.models:
            return {'error': 'Over/Under model not loaded'}
        
        return self.models['over_under'].predict(
            home_team_id, away_team_id, match_date
        )
    
    def predict_clean_sheets(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str
    ) -> Dict[str, Any]:
        """
        Get just Clean Sheet prediction.
        
        Convenience method if you only need clean sheets.
        """
        if 'clean_sheets' not in self.models:
            return {'error': 'Clean Sheets model not loaded'}
        
        return self.models['clean_sheets'].predict(
            home_team_id, away_team_id, match_date
        )
    
    def _create_summary(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of all predictions.
        
        Extracts key insights and highlights best betting opportunities.
        
        Args:
            predictions: Full predictions dict from predict_all()
            
        Returns:
            Summary dict with key insights
        """
        summary = {
            'predictions_count': len([k for k in predictions.keys() 
                                     if k not in ['match_info', 'summary']]),
            'high_confidence_bets': [],
            'insights': []
        }
        
        # Extract expected goals if available
        if 'over_under' in predictions and 'error' not in predictions['over_under']:
            ou = predictions['over_under']
            summary['expected_total_goals'] = ou.get('expected_total_goals', 0)
            summary['expected_home_goals'] = ou.get('expected_home_goals', 0)
            summary['expected_away_goals'] = ou.get('expected_away_goals', 0)
            
            # Add insight about total goals
            if ou.get('expected_total_goals', 0) > 3.5:
                summary['insights'].append("High-scoring game expected (3.5+ goals)")
            elif ou.get('expected_total_goals', 0) < 2.0:
                summary['insights'].append("Low-scoring game expected (<2 goals)")
        
        # Check for high-confidence BTTS bet
        if 'btts' in predictions and 'error' not in predictions['btts']:
            btts = predictions['btts']
            if btts.get('confidence', 0) >= 0.75:
                if btts.get('btts_yes_prob', 0) > 0.65:
                    summary['high_confidence_bets'].append({
                        'market': 'BTTS Yes',
                        'probability': btts['btts_yes_prob'],
                        'confidence': btts['confidence']
                    })
                    summary['insights'].append("Strong BTTS Yes opportunity")
                elif btts.get('btts_no_prob', 0) > 0.65:
                    summary['high_confidence_bets'].append({
                        'market': 'BTTS No',
                        'probability': btts['btts_no_prob'],
                        'confidence': btts['confidence']
                    })
                    summary['insights'].append("Strong BTTS No opportunity")
        
        # Check for high-confidence O/U bet
        if 'over_under' in predictions and 'error' not in predictions['over_under']:
            ou = predictions['over_under']
            if ou.get('confidence', 0) >= 0.75:
                if ou.get('over_prob', 0) > 0.65:
                    summary['high_confidence_bets'].append({
                        'market': f"Over {ou.get('goal_threshold', 2.5)}",
                        'probability': ou['over_prob'],
                        'confidence': ou['confidence']
                    })
                    summary['insights'].append(
                        f"Strong Over {ou.get('goal_threshold', 2.5)} opportunity"
                    )
                elif ou.get('under_prob', 0) > 0.65:
                    summary['high_confidence_bets'].append({
                        'market': f"Under {ou.get('goal_threshold', 2.5)}",
                        'probability': ou['under_prob'],
                        'confidence': ou['confidence']
                    })
                    summary['insights'].append(
                        f"Strong Under {ou.get('goal_threshold', 2.5)} opportunity"
                    )
        
        # Check for 0-0 possibility
        if 'clean_sheets' in predictions and 'error' not in predictions['clean_sheets']:
            cs = predictions['clean_sheets']
            if cs.get('both_clean_sheet_prob', 0) > 0.15:  # 15%+ chance of 0-0
                summary['insights'].append(
                    f"Significant 0-0 risk ({cs['both_clean_sheet_prob']:.1%})"
                )
        
        # Determine best bet
        if summary['high_confidence_bets']:
            # Sort by confidence × probability
            best = max(
                summary['high_confidence_bets'],
                key=lambda x: x['confidence'] * x['probability']
            )
            summary['best_bet'] = {
                'market': best['market'],
                'probability': best['probability'],
                'confidence': best['confidence']
            }
        else:
            summary['best_bet'] = None
            summary['insights'].append("No high-confidence betting opportunities")
        
        return summary
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about all loaded models.
        
        Returns:
            Dict with model metadata
        """
        info = {
            'factory_version': '1.0.0',
            'enabled_models': self.enabled_models,
            'model_count': len(self.models),
            'models': {}
        }
        
        for name, model in self.models.items():
            info['models'][name] = model.get_info()
        
        return info
    
    def print_predictions(
        self,
        predictions: Dict[str, Any],
        detailed: bool = False
    ):
        """
        Pretty-print predictions to console.
        
        Useful for debugging and manual analysis.
        
        Args:
            predictions: Predictions dict from predict_all()
            detailed: Whether to show detailed info or just summary
        """
        print("\n" + "="*70)
        print("MATCH PREDICTIONS")
        print("="*70)
        
        # Match info
        info = predictions.get('match_info', {})
        print(f"\nMatch: Team {info.get('home_team_id')} vs Team {info.get('away_team_id')}")
        print(f"Date: {info.get('match_date')}")
        if info.get('league'):
            print(f"League: {info.get('league')}")
        
        # Summary
        if 'summary' in predictions:
            summary = predictions['summary']
            print(f"\n{'─'*70}")
            print("SUMMARY")
            print(f"{'─'*70}")
            
            if summary.get('expected_total_goals'):
                print(f"Expected Total Goals: {summary['expected_total_goals']:.2f}")
            
            if summary.get('best_bet'):
                best = summary['best_bet']
                print(f"\n🎯 Best Bet: {best['market']}")
                print(f"   Probability: {best['probability']:.1%}")
                print(f"   Confidence: {best['confidence']:.1%}")
            
            if summary.get('insights'):
                print(f"\n💡 Insights:")
                for insight in summary['insights']:
                    print(f"   • {insight}")
        
        if detailed:
            # BTTS
            if 'btts' in predictions and 'error' not in predictions['btts']:
                btts = predictions['btts']
                print(f"\n{'─'*70}")
                print("BOTH TEAMS TO SCORE")
                print(f"{'─'*70}")
                print(f"Yes: {btts['btts_yes_prob']:.1%}")
                print(f"No: {btts['btts_no_prob']:.1%}")
                print(f"Confidence: {btts['confidence']:.1%}")
            
            # Over/Under
            if 'over_under' in predictions and 'error' not in predictions['over_under']:
                ou = predictions['over_under']
                print(f"\n{'─'*70}")
                print(f"OVER/UNDER {ou['goal_threshold']}")
                print(f"{'─'*70}")
                print(f"Over: {ou['over_prob']:.1%}")
                print(f"Under: {ou['under_prob']:.1%}")
                print(f"Expected Total: {ou['expected_total_goals']:.2f} goals")
                print(f"Confidence: {ou['confidence']:.1%}")
            
            # Clean Sheets
            if 'clean_sheets' in predictions and 'error' not in predictions['clean_sheets']:
                cs = predictions['clean_sheets']
                print(f"\n{'─'*70}")
                print("CLEAN SHEETS")
                print(f"{'─'*70}")
                print(f"Home CS: {cs['home_clean_sheet_prob']:.1%}")
                print(f"Away CS: {cs['away_clean_sheet_prob']:.1%}")
                print(f"0-0 Draw: {cs['both_clean_sheet_prob']:.1%}")
                print(f"Confidence: {cs['confidence']:.1%}")
        
        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    """
    Test the model factory.
    """
    print("\n" + "="*70)
    print("MODEL FACTORY TEST")
    print("="*70 + "\n")
    
    # Create factory
    factory = ModelFactory()
    
    # Get factory info
    print("Factory info:")
    info = factory.get_model_info()
    print(f"  Loaded {info['model_count']} models: {', '.join(info['enabled_models'])}")
    
    # Test predictions
    print("\n\nTesting predictions...")
    predictions = factory.predict_all(
        home_team_id=1,
        away_team_id=2,
        match_date='2024-01-15',
        league_name='Premier League'
    )
    
    # Print predictions
    factory.print_predictions(predictions, detailed=True)
    
    print("="*70)
    print("Model Factory working correctly!")
    print("="*70 + "\n")