"""
Team Statistics Calculator

Wrapper around team features with additional statistical analysis.
Calculates attack/defence strength, scoring patterns, and match style.

This goes beyond form (last 5 games) to look at longer-term patterns.

Usage:
    stats = TeamStatisticsCalculator()
    features = stats.calculate_match_statistics(home_id=1, away_id=2)
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from src.features.team_features import TeamFeatures
from src.data.database import Session, Team

# Logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class TeamStatisticsCalculator:
    """
    Calculates season-long statistical metrics for teams.
    
    Wraps TeamFeatures and adds extra statistical analysis.
    """
    
    def __init__(
        self,
        lookback_days: int = 90,
        min_games: int = 5
    ):
        """
        Initialise statistics calculator.
        
        Args:
            lookback_days: How many days of history to analyse
            min_games: Minimum games needed for valid stats
        """
        self.team_features = TeamFeatures(
            lookback_days=lookback_days,
            min_games=min_games
        )
        self.lookback_days = lookback_days
        self.min_games = min_games
        
        logger.info(
            f"Team Statistics Calculator initialised: "
            f"lookback={lookback_days} days, min_games={min_games}"
        )
    
    def calculate_match_statistics(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate statistical features for both teams.
        
        This gives you the fundamental attacking and defensive numbers.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date for backtesting
            
        Returns:
            Dictionary with statistical metrics:
            {
                'home_attack_strength': 1.35,  # Scores 35% more than avg
                'away_attack_strength': 0.92,  # Scores 8% less than avg
                'attack_differential': 0.43,
                'home_defence_strength': 0.85,  # Concedes 15% less (good)
                'away_defence_strength': 1.12,  # Concedes 12% more (bad)
                'defence_differential': -0.27,
                'home_goals_for_pg': 1.8,
                'away_goals_for_pg': 1.3,
                'home_goals_against_pg': 0.9,
                'away_goals_against_pg': 1.4,
                'home_clean_sheet_rate': 0.45,
                'away_clean_sheet_rate': 0.28,
                'home_btts_rate': 0.60,  # Both teams score in 60% of their games
                'away_btts_rate': 0.55,
                'home_over_25_rate': 0.65,  # Over 2.5 in 65% of their games
                'away_over_25_rate': 0.48,
                ...
            }
        """
        try:
            # Get match features from team features calculator
            # This does the heavy lifting
            match_features = self.team_features.calculate_match_features(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date
            )
            
            # Extract and organise features
            home_stats = match_features['home_features']
            away_stats = match_features['away_features']
            
            # Calculate additional derived metrics
            
            # Expected goal factors (attack vs defence matchup)
            # Home xG factor = home attack × away defence
            home_xg_factor = match_features['home_attack_vs_away_defence']
            away_xg_factor = match_features['away_attack_vs_home_defence']
            
            # Match style prediction
            match_style = self._predict_match_style(home_stats, away_stats)
            
            # Scoring probability (how likely each team is to score)
            home_score_probability = 1 - (home_stats['failed_to_score_rate'])
            away_score_probability = 1 - (away_stats['failed_to_score_rate'])
            
            return {
                # Attack strength (relative to league average)
                'home_attack_strength': home_stats['attack_strength'],
                'away_attack_strength': away_stats['attack_strength'],
                'attack_differential': match_features['attack_differential'],
                
                # Defence strength (relative to league average)
                'home_defence_strength': home_stats['defence_strength'],
                'away_defence_strength': away_stats['defence_strength'],
                'defence_differential': match_features['defence_differential'],
                
                # Goals per game
                'home_goals_for_pg': home_stats['goals_for_per_game'],
                'away_goals_for_pg': away_stats['goals_for_per_game'],
                'home_goals_against_pg': home_stats['goals_against_per_game'],
                'away_goals_against_pg': away_stats['goals_against_per_game'],
                
                # Clean sheets
                'home_clean_sheet_rate': home_stats['clean_sheet_rate'],
                'away_clean_sheet_rate': away_stats['clean_sheet_rate'],
                
                # Failed to score
                'home_failed_to_score_rate': home_stats['failed_to_score_rate'],
                'away_failed_to_score_rate': away_stats['failed_to_score_rate'],
                
                # Scoring probabilities
                'home_score_probability': home_score_probability,
                'away_score_probability': away_score_probability,
                'btts_likelihood': home_score_probability * away_score_probability,
                
                # Match patterns (BTTS, Over 2.5, etc.)
                'home_btts_rate': home_stats['btts_rate'],
                'away_btts_rate': away_stats['btts_rate'],
                'combined_btts_rate': (home_stats['btts_rate'] + away_stats['btts_rate']) / 2,
                
                'home_over_25_rate': home_stats['high_scoring_rate'],
                'away_over_25_rate': away_stats['high_scoring_rate'],
                'combined_over_25_rate': (home_stats['high_scoring_rate'] + away_stats['high_scoring_rate']) / 2,
                
                # Average goals in their matches
                'home_avg_match_goals': home_stats['avg_goals_per_match'],
                'away_avg_match_goals': away_stats['avg_goals_per_match'],
                
                # Expected goals factors (for Poisson model)
                'home_xg_factor': home_xg_factor,
                'away_xg_factor': away_xg_factor,
                'expected_goals_ratio': match_features['expected_goals_ratio'],
                
                # Match style prediction
                'predicted_match_style': match_style['style'],
                'expected_goals_total': match_style['expected_goals_total'],
                'expected_defensive_game': match_style['defensive'],
                'expected_high_scoring': match_style['high_scoring'],
                
                # Days since last match (fatigue/rest)
                'home_days_since_match': home_stats['days_since_last_match'],
                'away_days_since_match': away_stats['days_since_last_match'],
                
                # Sample sizes
                'home_games_analysed': home_stats['games_played'],
                'away_games_analysed': away_stats['games_played'],
                'lookback_days': self.lookback_days
            }
            
        except Exception as e:
            logger.error(f"Error calculating team statistics: {e}")
            return self._empty_features()
    
    def _predict_match_style(
        self,
        home_stats: Dict,
        away_stats: Dict
    ) -> Dict:
        """
        Predict match style based on team statistics.
        
        Args:
            home_stats: Home team statistics
            away_stats: Away team statistics
            
        Returns:
            {
                'style': 'high_scoring',  # high_scoring, defensive, balanced
                'expected_goals_total': 2.8,
                'defensive': False,
                'high_scoring': True
            }
        """
        # Average goals in matches involving these teams
        avg_goals = (
            home_stats['avg_goals_per_match'] +
            away_stats['avg_goals_per_match']
        ) / 2
        
        # Classify style
        if avg_goals >= 3.5:
            style = 'high_scoring'
            defensive = False
            high_scoring = True
        elif avg_goals <= 2.0:
            style = 'defensive'
            defensive = True
            high_scoring = False
        else:
            style = 'balanced'
            defensive = False
            high_scoring = False
        
        return {
            'style': style,
            'expected_goals_total': avg_goals,
            'defensive': defensive,
            'high_scoring': high_scoring
        }
    
    def get_head_to_head_stats(
        self,
        home_team_id: int,
        away_team_id: int,
        limit: int = 5
    ) -> Dict:
        """
        Get head-to-head statistics.
        
        Wrapper around team_features.get_head_to_head.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            limit: Number of past meetings to analyse
            
        Returns:
            Head-to-head statistics dict
        """
        return self.team_features.get_head_to_head(
            team_a_id=home_team_id,
            team_b_id=away_team_id,
            limit=limit
        )
    
    def _empty_features(self) -> Dict:
        """Return empty features when data unavailable."""
        return {
            'home_attack_strength': 1.0,
            'away_attack_strength': 1.0,
            'attack_differential': 0.0,
            'home_defence_strength': 1.0,
            'away_defence_strength': 1.0,
            'defence_differential': 0.0,
            'home_goals_for_pg': 1.5,
            'away_goals_for_pg': 1.5,
            'home_goals_against_pg': 1.5,
            'away_goals_against_pg': 1.5,
            'home_clean_sheet_rate': 0.33,
            'away_clean_sheet_rate': 0.33,
            'home_failed_to_score_rate': 0.25,
            'away_failed_to_score_rate': 0.25,
            'home_score_probability': 0.75,
            'away_score_probability': 0.75,
            'btts_likelihood': 0.56,
            'home_btts_rate': 0.5,
            'away_btts_rate': 0.5,
            'combined_btts_rate': 0.5,
            'home_over_25_rate': 0.5,
            'away_over_25_rate': 0.5,
            'combined_over_25_rate': 0.5,
            'home_avg_match_goals': 2.5,
            'away_avg_match_goals': 2.5,
            'home_xg_factor': 1.0,
            'away_xg_factor': 1.0,
            'expected_goals_ratio': 1.0,
            'predicted_match_style': 'balanced',
            'expected_goals_total': 2.5,
            'expected_defensive_game': False,
            'expected_high_scoring': False,
            'home_days_since_match': 7,
            'away_days_since_match': 7,
            'home_games_analysed': 0,
            'away_games_analysed': 0,
            'lookback_days': self.lookback_days
        }


if __name__ == '__main__':
    """Quick test."""
    print("Team Statistics Calculator Test\n")
    
    calc = TeamStatisticsCalculator(lookback_days=90)
    
    from src.data.database import Session, Team
    session = Session()
    teams = session.query(Team).order_by(Team.current_elo.desc()).limit(2).all()
    
    if len(teams) >= 2:
        features = calc.calculate_match_statistics(teams[0].id, teams[1].id)
        
        print(f"Match: {teams[0].name} vs {teams[1].name}\n")
        print(f"Home Attack: {features['home_attack_strength']:.2f}x league avg")
        print(f"Away Attack: {features['away_attack_strength']:.2f}x league avg")
        print(f"Home Defence: {features['home_defence_strength']:.2f}x league avg")
        print(f"Away Defence: {features['away_defence_strength']:.2f}x league avg")
        print(f"\nPredicted Style: {features['predicted_match_style']}")
        print(f"Expected Goals Total: {features['expected_goals_total']:.2f}")
        print(f"BTTS Likelihood: {features['btts_likelihood']:.1%}")
    
    session.close()
    print("\nTeam Statistics Calculator working correctly")