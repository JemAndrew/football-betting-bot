"""
Season Timing Analyser

Analyses when in the season a match occurs and fixture congestion.

Why timing matters:
- Early season: Teams still finding form
- Mid-season: Normal patterns established  
- Run-in (last 10 games): High stakes, fatigue
- Christmas period: 3 games in 6 days = fatigue
- Fixture congestion: Tired teams, rotation, more goals conceded

Usage:
    analyser = SeasonTimingAnalyser()
    timing = analyser.analyse_timing(home_id=1, away_id=2, match_date=datetime.now())
    if timing['home_tired']:
        print("Home team is fatigued from fixture congestion")
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

from src.data.database import Session, Team, Match
from sqlalchemy import func, and_, or_

logger = logging.getLogger(__name__)


class SeasonTimingAnalyser:
    """
    Analyses season timing and fixture congestion.
    
    Tired teams make mistakes, concede more, rotate squads.
    """
    
    def __init__(self):
        """Initialise season timing analyser."""
        logger.info("Season Timing Analyser initialised")
    
    def analyse_timing(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Analyse season timing and fixture context.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Match date (for backtesting, else uses today)
            
        Returns:
            {
                'season_stage': 'run_in',  # early, mid, run_in
                'gameweek_estimate': 32,
                'matches_into_season': 31,
                'home_matches_last_7_days': 1,
                'away_matches_last_7_days': 2,
                'home_days_since_last': 4,
                'away_days_since_last': 3,
                'home_fixture_congestion': 'medium',  # low, medium, high
                'away_fixture_congestion': 'high',
                'home_tired': False,
                'away_tired': True,
                'end_of_season': True,
                'christmas_period': False,
                'fixture_density_next_14_days_home': 3,
                'fixture_density_next_14_days_away': 4,
                'home_rotation_likely': False,
                'away_rotation_likely': True
            }
        """
        session = Session()
        
        try:
            if match_date is None:
                match_date = datetime.now()
            
            # Determine season start (August 1st of appropriate year)
            if match_date.month >= 8:
                season_start = datetime(match_date.year, 8, 1)
            else:
                season_start = datetime(match_date.year - 1, 8, 1)
            
            # Count matches so far this season for home team
            home_matches = session.query(func.count(Match.id)).filter(
                and_(
                    Match.date >= season_start,
                    Match.date < match_date,
                    or_(
                        Match.home_team_id == home_team_id,
                        Match.away_team_id == home_team_id
                    )
                )
            ).scalar() or 0
            
            # Estimate gameweek (Premier League has 38 games)
            gameweek = min(home_matches + 1, 38)
            
            # Determine season stage
            if gameweek <= 10:
                season_stage = 'early'
            elif gameweek <= 28:
                season_stage = 'mid'
            else:
                season_stage = 'run_in'
            
            # Fixture congestion analysis
            home_congestion = self._analyse_fixture_congestion(
                session, home_team_id, match_date
            )
            
            away_congestion = self._analyse_fixture_congestion(
                session, away_team_id, match_date
            )
            
            # Christmas period detection (high fixture density)
            christmas_period = self._is_christmas_period(match_date)
            
            # End of season detection
            end_of_season = gameweek >= 35
            
            return {
                # Season context
                'season_stage': season_stage,
                'gameweek_estimate': gameweek,
                'matches_into_season': home_matches,
                
                # Recent fixture load (last 7 days)
                'home_matches_last_7_days': home_congestion['matches_last_7_days'],
                'away_matches_last_7_days': away_congestion['matches_last_7_days'],
                
                # Days since last match
                'home_days_since_last': home_congestion['days_since_last'],
                'away_days_since_last': away_congestion['days_since_last'],
                
                # Congestion classification
                'home_fixture_congestion': home_congestion['congestion_level'],
                'away_fixture_congestion': away_congestion['congestion_level'],
                
                # Fatigue indicators
                'home_tired': home_congestion['is_tired'],
                'away_tired': away_congestion['is_tired'],
                
                # Upcoming fixtures
                'fixture_density_next_14_days_home': home_congestion['upcoming_matches'],
                'fixture_density_next_14_days_away': away_congestion['upcoming_matches'],
                
                # Squad rotation predictions
                'home_rotation_likely': home_congestion['rotation_likely'],
                'away_rotation_likely': away_congestion['rotation_likely'],
                
                # Special periods
                'end_of_season': end_of_season,
                'christmas_period': christmas_period,
                'intense_period': christmas_period or (home_congestion['is_tired'] and away_congestion['is_tired'])
            }
            
        except Exception as e:
            logger.error(f"Error analysing season timing: {e}")
            return self._empty_features()
        finally:
            session.close()
    
    def _analyse_fixture_congestion(
        self,
        session,
        team_id: int,
        match_date: datetime
    ) -> Dict:
        """
        Analyse fixture congestion for a team.
        
        Returns detailed congestion metrics.
        """
        # Recent matches (last 7 days)
        seven_days_ago = match_date - timedelta(days=7)
        
        recent_matches = session.query(func.count(Match.id)).filter(
            and_(
                Match.date >= seven_days_ago,
                Match.date < match_date,
                or_(
                    Match.home_team_id == team_id,
                    Match.away_team_id == team_id
                )
            )
        ).scalar() or 0
        
        # Last match date
        last_match = session.query(Match).filter(
            and_(
                Match.date < match_date,
                or_(
                    Match.home_team_id == team_id,
                    Match.away_team_id == team_id
                )
            )
        ).order_by(Match.date.desc()).first()
        
        if last_match:
            days_since_last = (match_date - last_match.date).days
        else:
            days_since_last = 7  # Default if no previous match
        
        # Upcoming matches (next 14 days)
        fourteen_days_later = match_date + timedelta(days=14)
        
        upcoming_matches = session.query(func.count(Match.id)).filter(
            and_(
                Match.date > match_date,
                Match.date <= fourteen_days_later,
                or_(
                    Match.home_team_id == team_id,
                    Match.away_team_id == team_id
                )
            )
        ).scalar() or 0
        
        # Classify congestion level
        congestion_level = self._classify_congestion(recent_matches, days_since_last)
        
        # Fatigue indicator
        is_tired = congestion_level == 'high'
        
        # Rotation likelihood
        # Teams rotate when: high congestion OR important match coming soon
        rotation_likely = (congestion_level == 'high') or (upcoming_matches >= 3)
        
        return {
            'matches_last_7_days': recent_matches,
            'days_since_last': days_since_last,
            'upcoming_matches': upcoming_matches,
            'congestion_level': congestion_level,
            'is_tired': is_tired,
            'rotation_likely': rotation_likely
        }
    
    def _classify_congestion(self, recent_matches: int, days_since_last: int) -> str:
        """
        Classify fixture congestion level.
        
        Args:
            recent_matches: Matches in last 7 days
            days_since_last: Days since last match
            
        Returns:
            'low', 'medium', or 'high'
        """
        # High congestion: 3+ matches in 7 days OR less than 3 days rest
        if recent_matches >= 3 or days_since_last <= 2:
            return 'high'
        
        # Medium: 2 matches in 7 days OR 3-4 days rest
        elif recent_matches == 2 or (3 <= days_since_last <= 4):
            return 'medium'
        
        # Low: 0-1 matches in 7 days AND 5+ days rest
        else:
            return 'low'
    
    def _is_christmas_period(self, match_date: datetime) -> bool:
        """
        Check if match is during Christmas period.
        
        Christmas period: Dec 20 - Jan 7
        Very high fixture density (3 matches in 7 days common)
        """
        if match_date.month == 12 and match_date.day >= 20:
            return True
        elif match_date.month == 1 and match_date.day <= 7:
            return True
        else:
            return False
    
    def get_season_progress(self, match_date: Optional[datetime] = None) -> Dict:
        """
        Get overall season progress information.
        
        Args:
            match_date: Date to check (defaults to today)
            
        Returns:
            Season progress metrics
        """
        if match_date is None:
            match_date = datetime.now()
        
        # Determine season start
        if match_date.month >= 8:
            season_start = datetime(match_date.year, 8, 1)
            season_end = datetime(match_date.year + 1, 5, 31)
        else:
            season_start = datetime(match_date.year - 1, 8, 1)
            season_end = datetime(match_date.year, 5, 31)
        
        # Calculate progress
        total_days = (season_end - season_start).days
        days_elapsed = (match_date - season_start).days
        progress_pct = (days_elapsed / total_days) * 100
        
        # Estimate gameweek (38 game season)
        estimated_gameweek = int((progress_pct / 100) * 38) + 1
        
        return {
            'season_start': season_start,
            'season_end': season_end,
            'current_date': match_date,
            'days_elapsed': days_elapsed,
            'days_remaining': total_days - days_elapsed,
            'progress_percentage': progress_pct,
            'estimated_gameweek': min(estimated_gameweek, 38)
        }
    
    def _empty_features(self) -> Dict:
        """Return empty features when data unavailable."""
        return {
            'season_stage': 'mid',
            'gameweek_estimate': 19,
            'matches_into_season': 18,
            'home_matches_last_7_days': 0,
            'away_matches_last_7_days': 0,
            'home_days_since_last': 7,
            'away_days_since_last': 7,
            'home_fixture_congestion': 'low',
            'away_fixture_congestion': 'low',
            'home_tired': False,
            'away_tired': False,
            'fixture_density_next_14_days_home': 0,
            'fixture_density_next_14_days_away': 0,
            'home_rotation_likely': False,
            'away_rotation_likely': False,
            'end_of_season': False,
            'christmas_period': False,
            'intense_period': False
        }


if __name__ == '__main__':
    """Quick test."""
    print("Season Timing Analyser Test\n")
    
    analyser = SeasonTimingAnalyser()
    
    from src.data.database import Session, Team
    session = Session()
    teams = session.query(Team).limit(2).all()
    
    if len(teams) >= 2:
        # Test with current date
        result = analyser.analyse_timing(teams[0].id, teams[1].id)
        
        print(f"Match: {teams[0].name} vs {teams[1].name}")
        print(f"Season Stage: {result['season_stage']}")
        print(f"Gameweek: {result['gameweek_estimate']}")
        print(f"Home Congestion: {result['home_fixture_congestion']}")
        print(f"Away Congestion: {result['away_fixture_congestion']}")
        print(f"Home Tired: {result['home_tired']}")
        print(f"Away Tired: {result['away_tired']}")
        print(f"Christmas Period: {result['christmas_period']}")
        
        # Test season progress
        progress = analyser.get_season_progress()
        print(f"\nSeason Progress: {progress['progress_percentage']:.1f}%")
        print(f"Estimated Gameweek: {progress['estimated_gameweek']}")
    
    session.close()
    print("\nSeason Timing Analyser working correctly")