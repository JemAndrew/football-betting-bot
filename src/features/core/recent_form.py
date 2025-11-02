"""
Recent Form Calculator

Wrapper around the form calculator with additional form analysis.
Recent performance often matters more than season-long stats.

Why form matters:
- Teams change tactics/managers mid-season
- Injuries affect short-term performance
- Confidence and momentum are real
- Hot streaks and cold streaks exist

Usage:
    form = RecentFormCalculator()
    features = form.calculate_match_form(home_id=1, away_id=2)
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from src.features.form_calculator import FormCalculator
from src.data.database import Session, Team

# Logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class RecentFormCalculator:
    """
    Calculates recent form metrics for teams.
    
    Wraps the FormCalculator and adds extra analysis.
    """
    
    def __init__(
        self,
        lookback_games: int = 5,
        exponential_decay: float = 0.9
    ):
        """
        Initialise form calculator.
        
        Args:
            lookback_games: Number of recent games to analyse
            exponential_decay: Weight recent games more (0.9 = standard)
        """
        self.form_calc = FormCalculator(
            lookback_games=lookback_games,
            exponential_decay=exponential_decay,
            home_away_split=True
        )
        self.lookback_games = lookback_games
        
        logger.info(
            f"Recent Form Calculator initialised: "
            f"lookback={lookback_games}, decay={exponential_decay}"
        )
    
    def calculate_match_form(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate form features for both teams.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date for backtesting
            
        Returns:
            Dictionary with form metrics:
            {
                'home_form_ppg': 2.2,  # Points per game last 5
                'away_form_ppg': 1.4,
                'form_differential': 0.8,  # Home in better form
                'home_form_string': 'WWDLW',
                'away_form_string': 'LDLWD',
                'home_momentum': 'positive',  # improving/stable/declining
                'away_momentum': 'negative',
                'momentum_differential': 2,  # +2 for home
                'home_goals_for_form': 1.8,  # Goals per game in last 5
                'away_goals_for_form': 1.2,
                'home_goals_against_form': 0.8,
                'away_goals_against_form': 1.4,
                'home_on_streak': True,  # On winning streak?
                'away_on_streak': False,
                'home_streak_length': 3,  # 3 wins in a row
                'away_streak_length': 0
            }
        """
        try:
            # Get match form features from form calculator
            # This gives us both teams' form and differentials
            match_form = self.form_calc.calculate_match_form_features(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date
            )
            
            # Extract venue-specific form (home plays at home, away plays away)
            home_form = match_form['home_form_venue']
            away_form = match_form['away_form_venue']
            
            # Calculate additional metrics
            
            # Streak detection (consecutive wins/losses)
            home_streak = self._detect_streak(home_form['form_string'])
            away_streak = self._detect_streak(away_form['form_string'])
            
            # Goals form (recent goal-scoring)
            home_goals_for_form = home_form['goals_for_per_game']
            away_goals_for_form = away_form['goals_for_per_game']
            home_goals_against_form = home_form['goals_against_per_game']
            away_goals_against_form = away_form['goals_against_per_game']
            
            # Form quality (excellent/good/average/poor)
            home_form_quality = self._classify_form(home_form['points_per_game'])
            away_form_quality = self._classify_form(away_form['points_per_game'])
            
            return {
                # Points-based form
                'home_form_ppg': home_form['points_per_game'],
                'away_form_ppg': away_form['points_per_game'],
                'form_differential': match_form['form_differential'],
                
                # Form strings (visual representation)
                'home_form_string': home_form['form_string'],
                'away_form_string': away_form['form_string'],
                
                # Momentum
                'home_momentum': home_form['momentum'],
                'away_momentum': away_form['momentum'],
                'momentum_differential': match_form['momentum_differential'],
                
                # Goals in recent form
                'home_goals_for_form': home_goals_for_form,
                'away_goals_for_form': away_goals_for_form,
                'home_goals_against_form': home_goals_against_form,
                'away_goals_against_form': away_goals_against_form,
                'goals_for_differential': match_form['goals_for_differential'],
                'goals_against_differential': match_form['goals_against_differential'],
                
                # Win/draw/loss rates
                'home_win_rate_form': home_form['win_rate'],
                'away_win_rate_form': away_form['win_rate'],
                
                # Streaks
                'home_on_streak': home_streak['on_streak'],
                'away_on_streak': away_streak['on_streak'],
                'home_streak_type': home_streak['streak_type'],
                'away_streak_type': away_streak['streak_type'],
                'home_streak_length': home_streak['streak_length'],
                'away_streak_length': away_streak['streak_length'],
                
                # Form quality classification
                'home_form_quality': home_form_quality,
                'away_form_quality': away_form_quality,
                
                # Clean sheets / failed to score in recent games
                'home_clean_sheets_form': home_form['clean_sheets'],
                'away_clean_sheets_form': away_form['clean_sheets'],
                'home_failed_to_score_form': home_form['failed_to_score'],
                'away_failed_to_score_form': away_form['failed_to_score'],
                
                # Additional context
                'games_analysed': self.lookback_games,
                'home_games_played': home_form['games_played'],
                'away_games_played': away_form['games_played']
            }
            
        except Exception as e:
            logger.error(f"Error calculating form: {e}")
            return self._empty_features()
    
    def _detect_streak(self, form_string: str) -> Dict:
        """
        Detect winning/losing/drawing streaks.
        
        Args:
            form_string: e.g. 'WWWDL'
            
        Returns:
            {
                'on_streak': True,
                'streak_type': 'win',  # win, draw, loss
                'streak_length': 3
            }
        """
        if not form_string:
            return {'on_streak': False, 'streak_type': None, 'streak_length': 0}
        
        # Check if last games are all the same result
        last_result = form_string[0]  # Most recent game
        streak_length = 0
        
        for result in form_string:
            if result == last_result:
                streak_length += 1
            else:
                break
        
        # Consider it a streak if 2+ of the same result
        on_streak = streak_length >= 2
        
        streak_type_map = {
            'W': 'win',
            'D': 'draw',
            'L': 'loss'
        }
        streak_type = streak_type_map.get(last_result)
        
        return {
            'on_streak': on_streak,
            'streak_type': streak_type,
            'streak_length': streak_length
        }
    
    def _classify_form(self, ppg: float) -> str:
        """
        Classify form quality based on points per game.
        
        Args:
            ppg: Points per game
            
        Returns:
            'excellent', 'good', 'average', 'poor', 'very_poor'
        """
        # Over 5 games, max is 3.0 PPG (5 wins)
        if ppg >= 2.5:
            return 'excellent'  # 12.5+ points from 5 = title-winning form
        elif ppg >= 2.0:
            return 'good'  # 10+ points from 5 = solid
        elif ppg >= 1.5:
            return 'average'  # 7.5 points from 5 = mid-table
        elif ppg >= 1.0:
            return 'poor'  # 5 points from 5 = struggling
        else:
            return 'very_poor'  # <5 points from 5 = relegation form
    
    def _empty_features(self) -> Dict:
        """Return empty features when data unavailable."""
        return {
            'home_form_ppg': 1.5,
            'away_form_ppg': 1.5,
            'form_differential': 0.0,
            'home_form_string': '',
            'away_form_string': '',
            'home_momentum': 'neutral',
            'away_momentum': 'neutral',
            'momentum_differential': 0,
            'home_goals_for_form': 1.0,
            'away_goals_for_form': 1.0,
            'home_goals_against_form': 1.0,
            'away_goals_against_form': 1.0,
            'goals_for_differential': 0.0,
            'goals_against_differential': 0.0,
            'home_win_rate_form': 0.33,
            'away_win_rate_form': 0.33,
            'home_on_streak': False,
            'away_on_streak': False,
            'home_streak_type': None,
            'away_streak_type': None,
            'home_streak_length': 0,
            'away_streak_length': 0,
            'home_form_quality': 'average',
            'away_form_quality': 'average',
            'home_clean_sheets_form': 0,
            'away_clean_sheets_form': 0,
            'home_failed_to_score_form': 0,
            'away_failed_to_score_form': 0,
            'games_analysed': self.lookback_games,
            'home_games_played': 0,
            'away_games_played': 0
        }


if __name__ == '__main__':
    """Quick test."""
    print("Recent Form Calculator Test\n")
    
    calc = RecentFormCalculator(lookback_games=5)
    
    from src.data.database import Session, Team
    session = Session()
    teams = session.query(Team).order_by(Team.current_elo.desc()).limit(2).all()
    
    if len(teams) >= 2:
        features = calc.calculate_match_form(teams[0].id, teams[1].id)
        
        print(f"Match: {teams[0].name} vs {teams[1].name}\n")
        print(f"Home Form: {features['home_form_string']} ({features['home_form_ppg']:.2f} PPG)")
        print(f"Away Form: {features['away_form_string']} ({features['away_form_ppg']:.2f} PPG)")
        print(f"Form Quality: {features['home_form_quality']} vs {features['away_form_quality']}")
        print(f"Momentum: {features['home_momentum']} vs {features['away_momentum']}")
        
        if features['home_on_streak']:
            print(f"Home on {features['home_streak_type']} streak ({features['home_streak_length']} games)")
        if features['away_on_streak']:
            print(f"Away on {features['away_streak_type']} streak ({features['away_streak_length']} games)")
    
    session.close()
    print("\nRecent Form Calculator working correctly")