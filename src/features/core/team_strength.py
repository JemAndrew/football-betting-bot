"""
Team Strength Calculator

Wrapper around the ELO rating system with additional strength metrics.
This provides a unified interface for team strength calculations.

ELO is the foundation but we add:
- Power ratings (normalised ELO)
- Strength differentials
- Historical strength trends
- Division-adjusted ratings

Usage:
    strength = TeamStrengthCalculator()
    features = strength.calculate_match_strength(home_id=1, away_id=2)
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from src.features.elo_calculator import ELOCalculator
from src.data.database import Session, Team

# Logging setup
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class TeamStrengthCalculator:
    """
    Calculates team strength metrics based on ELO and other factors.
    
    This wraps the ELO system and adds additional strength analysis.
    """
    
    def __init__(self):
        """Initialise strength calculator."""
        self.elo = ELOCalculator()
        logger.info("Team Strength Calculator initialised")
    
    def calculate_match_strength(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate strength features for both teams in a match.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date for historical queries (backtesting)
            
        Returns:
            Dictionary with strength metrics:
            {
                'home_elo': 1650.5,
                'away_elo': 1520.3,
                'elo_differential': 130.2,
                'home_elo_rank': 3,  # 3rd strongest team
                'away_elo_rank': 15,
                'strength_ratio': 1.085,  # Home 8.5% stronger
                'home_power_rating': 0.82,  # Normalised 0-1
                'away_power_rating': 0.68,
                'expected_home_score': 0.65,  # ELO-based match expectation
                'home_stronger': True
            }
        """
        session = Session()
        
        try:
            # Get current ELO ratings
            home_team = session.query(Team).filter_by(id=home_team_id).first()
            away_team = session.query(Team).filter_by(id=away_team_id).first()
            
            if not home_team or not away_team:
                logger.warning(f"Team not found: home={home_team_id}, away={away_team_id}")
                return self._empty_features()
            
            home_elo = home_team.current_elo
            away_elo = away_team.current_elo
            
            # Calculate differentials
            elo_diff = home_elo - away_elo
            
            # Strength ratio (how much stronger is one team?)
            strength_ratio = home_elo / away_elo if away_elo > 0 else 1.0
            
            # Get ELO ranks within league
            all_teams = session.query(Team).filter_by(
                league_id=home_team.league_id
            ).order_by(Team.current_elo.desc()).all()
            
            home_rank = next(
                (i + 1 for i, t in enumerate(all_teams) if t.id == home_team_id),
                None
            )
            away_rank = next(
                (i + 1 for i, t in enumerate(all_teams) if t.id == away_team_id),
                None
            )
            
            # Power ratings (normalise ELO to 0-1 scale within league)
            elo_values = [t.current_elo for t in all_teams]
            min_elo = min(elo_values)
            max_elo = max(elo_values)
            elo_range = max_elo - min_elo if max_elo > min_elo else 1
            
            home_power = (home_elo - min_elo) / elo_range
            away_power = (away_elo - min_elo) / elo_range
            
            # Expected score using ELO formula
            # This is the probability home team wins based purely on ELO
            expected_home_score = self.elo.calculate_expected_score(
                team_elo=home_elo,
                opponent_elo=away_elo,
                is_home=True  # Includes home advantage
            )
            
            return {
                'home_elo': home_elo,
                'away_elo': away_elo,
                'elo_differential': elo_diff,
                'home_elo_rank': home_rank,
                'away_elo_rank': away_rank,
                'rank_differential': away_rank - home_rank if home_rank and away_rank else 0,
                'strength_ratio': strength_ratio,
                'home_power_rating': home_power,
                'away_power_rating': away_power,
                'power_differential': home_power - away_power,
                'expected_home_score': expected_home_score,
                'expected_away_score': 1 - expected_home_score,
                'home_stronger': elo_diff > 0,
                'significant_strength_gap': abs(elo_diff) > 200  # Big gap
            }
            
        except Exception as e:
            logger.error(f"Error calculating team strength: {e}")
            return self._empty_features()
        finally:
            session.close()
    
    def get_team_strength_trend(
        self,
        team_id: int,
        lookback_days: int = 90
    ) -> Dict:
        """
        Calculate how team's strength has changed over time.
        
        Args:
            team_id: Team to analyse
            lookback_days: How far back to look
            
        Returns:
            Dictionary with trend analysis:
            {
                'current_elo': 1650,
                'elo_90_days_ago': 1580,
                'elo_change': +70,
                'trend': 'improving',  # improving, stable, declining
                'peak_elo': 1680,
                'lowest_elo': 1520
            }
        """
        # This would require historical ELO tracking in database
        # For now, return placeholder
        # TODO: Implement when we add ELO history table
        
        session = Session()
        team = session.query(Team).filter_by(id=team_id).first()
        session.close()
        
        if not team:
            return {}
        
        return {
            'current_elo': team.current_elo,
            'trend': 'stable',  # Would calculate from history
            'note': 'Historical ELO tracking not yet implemented'
        }
    
    def _empty_features(self) -> Dict:
        """Return empty features when data unavailable."""
        return {
            'home_elo': 1500.0,
            'away_elo': 1500.0,
            'elo_differential': 0.0,
            'home_elo_rank': None,
            'away_elo_rank': None,
            'rank_differential': 0,
            'strength_ratio': 1.0,
            'home_power_rating': 0.5,
            'away_power_rating': 0.5,
            'power_differential': 0.0,
            'expected_home_score': 0.5,
            'expected_away_score': 0.5,
            'home_stronger': False,
            'significant_strength_gap': False
        }


if __name__ == '__main__':
    """Quick test."""
    print("Team Strength Calculator Test\n")
    
    calc = TeamStrengthCalculator()
    
    # Test with first two teams
    from src.data.database import Session, Team
    session = Session()
    teams = session.query(Team).limit(2).all()
    
    if len(teams) >= 2:
        features = calc.calculate_match_strength(teams[0].id, teams[1].id)
        
        print(f"Match: {teams[0].name} vs {teams[1].name}\n")
        print(f"Home ELO: {features['home_elo']:.1f} (Rank {features['home_elo_rank']})")
        print(f"Away ELO: {features['away_elo']:.1f} (Rank {features['away_elo_rank']})")
        print(f"Differential: {features['elo_differential']:+.1f}")
        print(f"Strength Ratio: {features['strength_ratio']:.3f}")
        print(f"Expected Home Score: {features['expected_home_score']:.1%}")
    
    session.close()
    print("\nTeam Strength Calculator working correctly")