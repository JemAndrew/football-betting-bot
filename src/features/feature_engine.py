"""
Feature Engine - Combines All Features

This is the master orchestrator that combines all feature calculators.
Models call this to get a complete feature vector for any match.

Why we need this:
- Models shouldn't import 10 different feature classes
- Features should be calculated consistently
- Easy to add/remove features without touching models
- Single source of truth for feature calculation

Architecture:
    feature_engine.py (this file)
    ├── core/
    │   ├── elo_calculator.py       → Team strength (ELO)
    │   ├── form_calculator.py      → Recent form (last 5-10 games)
    │   └── team_statistics.py      → Attack/defence strength
    └── match_context/
        ├── head_to_head.py         → H2H history
        ├── importance.py           → Match stakes
        ├── rivalry.py              → Derby detection
        └── season_timing.py        → Season phase

Usage:
    engine = FeatureEngine()
    
    # Get all features for a match
    features = engine.get_match_features(
        home_team_id=1,
        away_team_id=2,
        match_date='2024-01-15'
    )
    
    # Returns dict with all features:
    # {
    #     'home_elo': 1650,
    #     'away_elo': 1580,
    #     'home_form': 2.2,
    #     'away_form': 1.8,
    #     'home_attack_strength': 1.15,
    #     'away_defence_strength': 0.92,
    #     ... etc
    # }
"""

from typing import Dict, Optional, Any
from datetime import datetime
import logging

# Core features
from src.features.core.elo_calculator import ELOCalculator
from src.features.core.form_calculator import FormCalculator
from src.features.core.team_statistics import TeamStatisticsCalculator

# Match context features
from src.features.match_context.head_to_head import HeadToHeadAnalyser
from src.features.match_context.importance import ImportanceCalculator
from src.features.match_context.rivalry import RivalryDetector
from src.features.match_context.season_timing import SeasonTimingAnalyser

# Database
from src.data.database import Session, Team, Match

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    Master feature orchestrator.
    
    Combines all feature calculators into a single interface.
    This is what your models will import and use.
    """
    
    def __init__(
        self,
        elo_k_factor: int = 20,
        form_lookback: int = 5,
        stats_lookback_days: int = 90,
        h2h_lookback_matches: int = 10
    ):
        """
        Initialise the feature engine.
        
        Args:
            elo_k_factor: K-factor for ELO updates (20 = standard)
            form_lookback: Number of recent games for form (5-10 typical)
            stats_lookback_days: Days of history for team stats (90 = ~3 months)
            h2h_lookback_matches: Number of H2H matches to analyse (10 typical)
        """
        logger.info("Initialising Feature Engine...")
        
        # Core features
        self.elo = ELOCalculator(k_factor=elo_k_factor)
        self.form = FormCalculator()
        self.team_stats = TeamStatisticsCalculator(
            lookback_days=stats_lookback_days,
            min_games=5
        )
        
        # Match context features
        self.h2h = HeadToHeadAnalyser(lookback_matches=h2h_lookback_matches)
        self.importance = ImportanceCalculator()
        self.rivalry = RivalryDetector()
        self.season_timing = SeasonTimingAnalyser()
        
        logger.info("✅ Feature Engine initialised successfully")
        logger.info(f"   - ELO K-factor: {elo_k_factor}")
        logger.info(f"   - Form lookback: {form_lookback} games")
        logger.info(f"   - Stats lookback: {stats_lookback_days} days")
        logger.info(f"   - H2H lookback: {h2h_lookback_matches} matches")
    
    def get_match_features(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        league_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get complete feature vector for a match.
        
        This is the main method that models will call.
        It combines all feature calculators into one feature dict.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            match_date: Match date (YYYY-MM-DD format)
            league_id: Optional league ID for league-specific features
            
        Returns:
            Dict containing all features for the match:
            {
                # ELO features
                'home_elo': float,
                'away_elo': float,
                'elo_diff': float,
                
                # Form features  
                'home_form': float,
                'away_form': float,
                'home_form_home': float,
                'away_form_away': float,
                
                # Team statistics
                'home_attack_strength': float,
                'home_defence_strength': float,
                'away_attack_strength': float,
                'away_defence_strength': float,
                'home_goals_for_avg': float,
                'home_goals_against_avg': float,
                'away_goals_for_avg': float,
                'away_goals_against_avg': float,
                
                # H2H features
                'h2h_home_wins': int,
                'h2h_away_wins': int,
                'h2h_draws': int,
                'h2h_home_goals_avg': float,
                'h2h_away_goals_avg': float,
                
                # Match context
                'is_rivalry': bool,
                'is_derby': bool,
                'home_importance': float,
                'away_importance': float,
                'season_phase': str,
                'is_congested_period': bool,
            }
        """
        logger.info(f"Calculating features for match: {home_team_id} vs {away_team_id}")
        
        features = {}
        
        # Parse date
        if isinstance(match_date, str):
            match_date = datetime.strptime(match_date, '%Y-%m-%d')
        
        # 1. ELO features
        try:
            home_elo = self.elo.get_team_elo(home_team_id)
            away_elo = self.elo.get_team_elo(away_team_id)
            
            features.update({
                'home_elo': home_elo,
                'away_elo': away_elo,
                'elo_diff': home_elo - away_elo,
                'elo_diff_abs': abs(home_elo - away_elo)
            })
            logger.debug(f"✅ ELO features calculated")
        except Exception as e:
            logger.error(f"❌ ELO calculation failed: {e}")
            features.update({
                'home_elo': 1500,  # Default ELO
                'away_elo': 1500,
                'elo_diff': 0,
                'elo_diff_abs': 0
            })
        
        # 2. Form features
        try:
            home_form = self.form.calculate_team_form(home_team_id, as_of_date=match_date)
            away_form = self.form.calculate_team_form(away_team_id, as_of_date=match_date)
            
            features.update({
                'home_form_points': home_form.get('points', 0),
                'away_form_points': away_form.get('points', 0),
                'home_form_home_points': home_form.get('home_points', 0),
                'away_form_away_points': away_form.get('away_points', 0),
                'form_diff': home_form.get('points', 0) - away_form.get('points', 0)
            })
            logger.debug(f"✅ Form features calculated")
        except Exception as e:
            logger.error(f"❌ Form calculation failed: {e}")
            features.update({
                'home_form_points': 0,
                'away_form_points': 0,
                'home_form_home_points': 0,
                'away_form_away_points': 0,
                'form_diff': 0
            })
        
        # 3. Team statistics (attack/defence strength)
        try:
            match_stats = self.team_stats.calculate_match_statistics(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date
            )
            
            features.update({
                'home_attack_strength': match_stats.get('home_attack_strength', 1.0),
                'home_defence_strength': match_stats.get('home_defence_strength', 1.0),
                'away_attack_strength': match_stats.get('away_attack_strength', 1.0),
                'away_defence_strength': match_stats.get('away_defence_strength', 1.0),
                'home_goals_for_avg': match_stats.get('home_goals_for_avg', 0),
                'home_goals_against_avg': match_stats.get('home_goals_against_avg', 0),
                'away_goals_for_avg': match_stats.get('away_goals_for_avg', 0),
                'away_goals_against_avg': match_stats.get('away_goals_against_avg', 0),
            })
            logger.debug(f"✅ Team statistics calculated")
        except Exception as e:
            logger.error(f"❌ Team statistics calculation failed: {e}")
            features.update({
                'home_attack_strength': 1.0,
                'home_defence_strength': 1.0,
                'away_attack_strength': 1.0,
                'away_defence_strength': 1.0,
                'home_goals_for_avg': 0,
                'home_goals_against_avg': 0,
                'away_goals_for_avg': 0,
                'away_goals_against_avg': 0,
            })
        
        # 4. Head-to-head features
        try:
            h2h = self.h2h.analyse_h2h(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                as_of_date=match_date
            )
            
            features.update({
                'h2h_matches_played': h2h.get('matches_played', 0),
                'h2h_home_wins': h2h.get('home_wins', 0),
                'h2h_away_wins': h2h.get('away_wins', 0),
                'h2h_draws': h2h.get('draws', 0),
                'h2h_home_goals_avg': h2h.get('home_goals_avg', 0),
                'h2h_away_goals_avg': h2h.get('away_goals_avg', 0),
                'h2h_total_goals_avg': h2h.get('total_goals_avg', 0),
            })
            logger.debug(f"✅ H2H features calculated")
        except Exception as e:
            logger.error(f"❌ H2H calculation failed: {e}")
            features.update({
                'h2h_matches_played': 0,
                'h2h_home_wins': 0,
                'h2h_away_wins': 0,
                'h2h_draws': 0,
                'h2h_home_goals_avg': 0,
                'h2h_away_goals_avg': 0,
                'h2h_total_goals_avg': 0,
            })
        
        # 5. Rivalry detection
        try:
            rivalry_info = self.rivalry.detect_rivalry(
                home_team_id=home_team_id,
                away_team_id=away_team_id
            )
            
            features.update({
                'is_rivalry': rivalry_info.get('is_rivalry', False),
                'is_derby': rivalry_info.get('is_derby', False),
                'rivalry_type': rivalry_info.get('rivalry_type', 'none'),
            })
            logger.debug(f"✅ Rivalry features calculated")
        except Exception as e:
            logger.error(f"❌ Rivalry detection failed: {e}")
            features.update({
                'is_rivalry': False,
                'is_derby': False,
                'rivalry_type': 'none',
            })
        
        # 6. Match importance
        try:
            importance = self.importance.calculate_importance(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date
            )
            
            features.update({
                'home_importance': importance.get('home_importance', 0),
                'away_importance': importance.get('away_importance', 0),
                'match_importance': importance.get('match_importance', 0),
            })
            logger.debug(f"✅ Importance features calculated")
        except Exception as e:
            logger.error(f"❌ Importance calculation failed: {e}")
            features.update({
                'home_importance': 0,
                'away_importance': 0,
                'match_importance': 0,
            })
        
        # 7. Season timing
        try:
            timing = self.season_timing.analyse_timing(match_date=match_date)
            
            features.update({
                'season_phase': timing.get('phase', 'unknown'),
                'games_played': timing.get('games_played', 0),
                'games_remaining': timing.get('games_remaining', 0),
                'is_congested_period': timing.get('is_congested', False),
            })
            logger.debug(f"✅ Season timing features calculated")
        except Exception as e:
            logger.error(f"❌ Season timing calculation failed: {e}")
            features.update({
                'season_phase': 'unknown',
                'games_played': 0,
                'games_remaining': 0,
                'is_congested_period': False,
            })
        
        logger.info(f"✅ Feature calculation complete: {len(features)} features")
        return features
    
    def get_feature_names(self) -> list:
        """
        Get list of all feature names.
        
        Useful for ML models that need to know feature order.
        
        Returns:
            List of feature name strings
        """
        # This will match the keys from get_match_features()
        return [
            # ELO
            'home_elo', 'away_elo', 'elo_diff', 'elo_diff_abs',
            
            # Form
            'home_form_points', 'away_form_points',
            'home_form_home_points', 'away_form_away_points', 'form_diff',
            
            # Team stats
            'home_attack_strength', 'home_defence_strength',
            'away_attack_strength', 'away_defence_strength',
            'home_goals_for_avg', 'home_goals_against_avg',
            'away_goals_for_avg', 'away_goals_against_avg',
            
            # H2H
            'h2h_matches_played', 'h2h_home_wins', 'h2h_away_wins', 'h2h_draws',
            'h2h_home_goals_avg', 'h2h_away_goals_avg', 'h2h_total_goals_avg',
            
            # Context
            'is_rivalry', 'is_derby', 'rivalry_type',
            'home_importance', 'away_importance', 'match_importance',
            'season_phase', 'games_played', 'games_remaining', 'is_congested_period',
        ]
    
    def get_feature_vector(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        categorical_encoding: str = 'label'
    ) -> list:
        """
        Get features as a list (for ML models).
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            match_date: Match date
            categorical_encoding: How to encode categorical features
                - 'label': Convert to numbers (0, 1, 2, ...)
                - 'onehot': One-hot encoding (not implemented yet)
                
        Returns:
            List of feature values in consistent order
        """
        features = self.get_match_features(home_team_id, away_team_id, match_date)
        feature_names = self.get_feature_names()
        
        # Convert dict to list in correct order
        vector = []
        for name in feature_names:
            value = features.get(name, 0)
            
            # Handle categorical features
            if isinstance(value, str):
                if categorical_encoding == 'label':
                    # Simple label encoding for now
                    # You can make this more sophisticated later
                    if name == 'season_phase':
                        phase_map = {'early': 0, 'mid': 1, 'late': 2, 'unknown': -1}
                        value = phase_map.get(value, -1)
                    elif name == 'rivalry_type':
                        rivalry_map = {'none': 0, 'local': 1, 'historic': 2, 'both': 3}
                        value = rivalry_map.get(value, 0)
                    else:
                        value = 0
            
            # Handle booleans
            elif isinstance(value, bool):
                value = int(value)
            
            vector.append(value)
        
        return vector


# Convenience function for quick access
def get_features_for_match(home_id: int, away_id: int, date: str) -> Dict[str, Any]:
    """
    Quick helper function to get features.
    
    Usage:
        features = get_features_for_match(1, 2, '2024-01-15')
    """
    engine = FeatureEngine()
    return engine.get_match_features(home_id, away_id, date)


if __name__ == "__main__":
    """
    Test the feature engine.
    """
    import sys
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("FEATURE ENGINE TEST")
    print("="*60 + "\n")
    
    # Create engine
    engine = FeatureEngine()
    
    # Test with sample match
    print("\n🧪 Testing feature extraction...")
    print("Match: Team 1 (home) vs Team 2 (away)")
    print("Date: 2024-01-15\n")
    
    try:
        features = engine.get_match_features(
            home_team_id=1,
            away_team_id=2,
            match_date='2024-01-15'
        )
        
        print(f"✅ SUCCESS: Extracted {len(features)} features")
        print("\nSample features:")
        for key, value in list(features.items())[:10]:
            print(f"  {key}: {value}")
        print("  ...")
        
        # Test feature vector
        print("\n🧪 Testing feature vector...")
        vector = engine.get_feature_vector(1, 2, '2024-01-15')
        print(f"✅ Feature vector length: {len(vector)}")
        print(f"   First 5 values: {vector[:5]}")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60 + "\n")