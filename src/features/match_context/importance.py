"""
Match Importance Calculator

Calculates how important a match is based on league standings.

High-stakes matches tend to be:
- More defensive (teams play cautiously)
- Lower scoring
- More unpredictable

Examples:
- Title decider between 1st and 2nd = Very important
- Mid-table clash with nothing to play for = Low importance
- Relegation six-pointer = Very important
- Champions League spot chase = Important

Usage:
    importance = MatchImportanceCalculator()
    score = importance.calculate_importance(home_id=1, away_id=2)
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from src.data.database import Session, Team, Match
from sqlalchemy import func

logger = logging.getLogger(__name__)


class MatchImportanceCalculator:
    """
    Calculates match importance based on league context.
    
    Importance affects how teams play - high stakes = defensive.
    """
    
    def __init__(self):
        """Initialise importance calculator."""
        logger.info("Match Importance Calculator initialised")
    
    def calculate_importance(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate how important this match is.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date for historical context
            
        Returns:
            {
                'importance_score': 7.5,  # 0-10 scale
                'home_fighting_for': 'champions_league',
                'away_fighting_for': 'survival',
                'is_top_clash': False,
                'is_bottom_clash': True,
                'is_mid_table': False,
                'points_gap': 12,  # Points between teams
                'home_position': 8,
                'away_position': 18,
                'high_stakes': True
            }
        """
        session = Session()
        
        try:
            # Get teams
            home_team = session.query(Team).filter_by(id=home_team_id).first()
            away_team = session.query(Team).filter_by(id=away_team_id).first()
            
            if not home_team or not away_team:
                return self._empty_features()
            
            # Get current league standings
            # This is simplified - in reality you'd calculate from match results
            standings = self._get_league_standings(
                session, home_team.league_id, match_date
            )
            
            # Find positions
            home_pos = self._get_team_position(standings, home_team_id)
            away_pos = self._get_team_position(standings, away_team_id)
            
            # Get points (simplified - using ELO as proxy for now)
            # TODO: Calculate actual points from matches
            home_points = self._estimate_points_from_elo(home_team.current_elo)
            away_points = self._estimate_points_from_elo(away_team.current_elo)
            points_gap = abs(home_points - away_points)
            
            # Determine what each team is fighting for
            home_objective = self._determine_objective(home_pos, len(standings))
            away_objective = self._determine_objective(away_pos, len(standings))
            
            # Calculate importance score (0-10)
            importance = self._calculate_importance_score(
                home_pos, away_pos, home_objective, away_objective, points_gap
            )
            
            # Classify match type
            is_top_clash = home_pos <= 6 and away_pos <= 6
            is_bottom_clash = home_pos >= 15 and away_pos >= 15
            is_mid_table = not is_top_clash and not is_bottom_clash
            
            return {
                'importance_score': importance,
                'home_fighting_for': home_objective,
                'away_fighting_for': away_objective,
                'is_top_clash': is_top_clash,
                'is_bottom_clash': is_bottom_clash,
                'is_mid_table': is_mid_table,
                'points_gap': points_gap,
                'home_position': home_pos,
                'away_position': away_pos,
                'position_differential': abs(home_pos - away_pos),
                'high_stakes': importance >= 7.0,
                'medium_stakes': 4.0 <= importance < 7.0,
                'low_stakes': importance < 4.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating match importance: {e}")
            return self._empty_features()
        finally:
            session.close()
    
    def _get_league_standings(self, session, league_id: int, date: Optional[datetime]) -> list:
        """Get league standings (simplified version)."""
        # Get all teams in league, ordered by ELO (proxy for position)
        teams = session.query(Team).filter_by(
            league_id=league_id
        ).order_by(Team.current_elo.desc()).all()
        
        return teams
    
    def _get_team_position(self, standings: list, team_id: int) -> int:
        """Get team's position in standings."""
        for i, team in enumerate(standings, 1):
            if team.id == team_id:
                return i
        return 10  # Default mid-table
    
    def _estimate_points_from_elo(self, elo: float) -> int:
        """Rough estimate of league points from ELO."""
        # Simplified: ELO 1700 = ~80 points, ELO 1300 = ~30 points
        # Linear approximation
        return int((elo - 1200) / 10)
    
    def _determine_objective(self, position: int, league_size: int) -> str:
        """Determine what a team is fighting for based on position."""
        if position <= 2:
            return 'title'
        elif position <= 4:
            return 'champions_league'
        elif position <= 7:
            return 'europa_league'
        elif position >= league_size - 2:
            return 'survival'
        elif position >= league_size - 5:
            return 'avoiding_relegation'
        else:
            return 'mid_table'
    
    def _calculate_importance_score(
        self,
        home_pos: int,
        away_pos: int,
        home_obj: str,
        away_obj: str,
        points_gap: int
    ) -> float:
        """
        Calculate importance on 0-10 scale.
        
        High importance situations:
        - Both fighting for title
        - Both fighting relegation
        - Close in standings
        - Direct rivals for same objective
        """
        importance = 5.0  # Base score
        
        # Title race boost
        if home_obj == 'title' and away_obj == 'title':
            importance = 9.5
        elif home_obj == 'title' or away_obj == 'title':
            importance = 8.0
        
        # Champions League race
        if home_obj == 'champions_league' and away_obj == 'champions_league':
            importance = 8.5
        elif home_obj == 'champions_league' or away_obj == 'champions_league':
            importance = 7.5
        
        # Relegation battle
        if home_obj == 'survival' and away_obj == 'survival':
            importance = 9.0  # Six-pointer
        elif home_obj in ['survival', 'avoiding_relegation'] or away_obj in ['survival', 'avoiding_relegation']:
            importance = 7.5
        
        # Mid-table (low importance)
        if home_obj == 'mid_table' and away_obj == 'mid_table':
            importance = 3.0
        
        # Adjust for position proximity (closer = more important)
        position_diff = abs(home_pos - away_pos)
        if position_diff <= 2:
            importance += 1.0
        elif position_diff >= 10:
            importance -= 1.0
        
        # Adjust for points gap (closer = more important)
        if points_gap <= 3:
            importance += 0.5
        elif points_gap >= 15:
            importance -= 0.5
        
        # Clamp to 0-10
        return max(0.0, min(10.0, importance))
    
    def _empty_features(self) -> Dict:
        """Return empty features."""
        return {
            'importance_score': 5.0,
            'home_fighting_for': 'mid_table',
            'away_fighting_for': 'mid_table',
            'is_top_clash': False,
            'is_bottom_clash': False,
            'is_mid_table': True,
            'points_gap': 0,
            'home_position': 10,
            'away_position': 10,
            'position_differential': 0,
            'high_stakes': False,
            'medium_stakes': True,
            'low_stakes': False
        }


if __name__ == '__main__':
    """Quick test."""
    print("Match Importance Calculator Test\n")
    
    calc = MatchImportanceCalculator()
    
    from src.data.database import Session, Team
    session = Session()
    teams = session.query(Team).order_by(Team.current_elo.desc()).limit(2).all()
    
    if len(teams) >= 2:
        result = calc.calculate_importance(teams[0].id, teams[1].id)
        print(f"Match: {teams[0].name} vs {teams[1].name}")
        print(f"Importance: {result['importance_score']:.1f}/10")
        print(f"Home fighting for: {result['home_fighting_for']}")
        print(f"Away fighting for: {result['away_fighting_for']}")
        print(f"High stakes: {result['high_stakes']}")
    
    session.close()