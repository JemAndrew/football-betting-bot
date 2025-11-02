"""
Form Calculator - Tracks Recent Team Performance

This calculates how teams have been performing in their last N games.
Form is often more predictive than overall season stats because:
- Teams change tactics/managers mid-season
- Injuries affect performance temporarily
- Confidence/momentum matters (hot streaks, slumps)
- Recent form beats historical averages for short-term predictions

Key metrics:
- Points from last 5 games (W=3, D=1, L=0)
- Home form vs away form (some teams way better at home)
- Goals scored/conceded recently
- Win/draw/loss record
- Exponential weighting (yesterday matters more than 2 weeks ago)

Usage:
    form_calc = FormCalculator(lookback_games=5)
    home_form = form_calc.calculate_team_form(team_id=1, is_home=True)
    away_form = form_calc.calculate_team_form(team_id=2, is_home=False)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import math

import logging
from src.data.database import Session, Team, Match

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FormCalculator:
    """
    Calculates recent form for teams based on their last N matches.
    
    Recent form often predicts better than season-long stats because
    teams change throughout the season (injuries, tactics, confidence).
    """
    
    def __init__(
        self,
        lookback_games: int = 5,
        exponential_decay: float = 0.9,
        home_away_split: bool = True
    ):
        """
        Initialise form calculator.
        
        Args:
            lookback_games: How many recent games to consider (usually 5-10)
            exponential_decay: Weight recent games more (0.9 = 10% decay per game back)
                              1.0 = all games equal, 0.8 = heavier decay
            home_away_split: Whether to calculate separate home/away form
                           True = more accurate but need more data
        """
        self.lookback_games = lookback_games
        self.exponential_decay = exponential_decay
        self.home_away_split = home_away_split
        
        logger.info(
            f"Form Calculator initialised: Lookback={lookback_games}, "
            f"Decay={exponential_decay}, Home/Away Split={home_away_split}"
        )
    
    def get_recent_matches(
        self,
        team_id: int,
        before_date: Optional[datetime] = None,
        is_home: Optional[bool] = None,
        limit: Optional[int] = None
    ) -> List[Match]:
        """
        Get team's recent matches in reverse chronological order.
        
        This is the core data fetching function. We need matches BEFORE a certain
        date to avoid lookahead bias (can't use future data to predict past).
        
        Args:
            team_id: Team to get matches for
            before_date: Only get matches before this date (for backtesting)
                        If None, uses current time
            is_home: Filter to home matches only (True) or away only (False)
                    None = both home and away
            limit: Max number of matches to return (None = all matches)
            
        Returns:
            List of Match objects, newest first
        """
        session = Session()
        
        try:
            # Build query - matches where team played (home or away)
            query = session.query(Match).filter(
                Match.status == 'FINISHED',
                (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
            )
            
            # Filter by date if specified (critical for backtesting)
            if before_date:
                query = query.filter(Match.date < before_date)
            
            # Filter by home/away if specified
            if is_home is not None:
                if is_home:
                    query = query.filter(Match.home_team_id == team_id)
                else:
                    query = query.filter(Match.away_team_id == team_id)
            
            # Get matches in reverse chronological order (newest first)
            matches = query.order_by(Match.date.desc())
            
            # Apply limit if specified
            if limit:
                matches = matches.limit(limit)
            
            return matches.all()
            
        finally:
            session.close()
    
    def calculate_match_result(
        self,
        match: Match,
        team_id: int
    ) -> Tuple[str, int, int, int]:
        """
        Determine result from team's perspective.
        
        Returns W/D/L and goals for/against from this team's viewpoint.
        
        Args:
            match: Match object
            team_id: Which team's perspective (home or away?)
            
        Returns:
            Tuple of (result, goals_for, goals_against, points)
            result: 'W', 'D', or 'L'
            goals_for: Goals this team scored
            goals_against: Goals this team conceded
            points: 3 for win, 1 for draw, 0 for loss
        """
        # Figure out if team was home or away
        is_home = (match.home_team_id == team_id)
        
        if is_home:
            goals_for = match.home_goals
            goals_against = match.away_goals
        else:
            goals_for = match.away_goals
            goals_against = match.home_goals
        
        # Determine result
        if goals_for > goals_against:
            result = 'W'
            points = 3
        elif goals_for == goals_against:
            result = 'D'
            points = 1
        else:
            result = 'L'
            points = 0
        
        return result, goals_for, goals_against, points
    
    def calculate_exponential_weights(
        self,
        num_games: int
    ) -> List[float]:
        """
        Calculate exponential decay weights for recent games.
        
        Most recent game gets weight 1.0, then each game back gets multiplied
        by decay factor. This means yesterday's 2-0 win matters more than
        a 2-0 win from 6 weeks ago.
        
        Args:
            num_games: How many games to weight
            
        Returns:
            List of weights, [1.0, 0.9, 0.81, 0.73, ...] for decay=0.9
            
        Example:
            With decay=0.9 and 5 games:
            Game 1 (most recent): 1.0
            Game 2: 0.9
            Game 3: 0.81
            Game 4: 0.73
            Game 5: 0.66
        """
        weights = []
        for i in range(num_games):
            weight = math.pow(self.exponential_decay, i)
            weights.append(weight)
        
        return weights
    
    def calculate_team_form(
        self,
        team_id: int,
        before_date: Optional[datetime] = None,
        is_home: Optional[bool] = None
    ) -> Dict:
        """
        Calculate comprehensive form metrics for a team.
        
        This is the main function you'll use. Returns everything you need
        to know about recent team performance.
        
        Args:
            team_id: Team to analyse
            before_date: Calculate form as of this date (None = now)
            is_home: Calculate home form (True), away form (False), or both (None)
            
        Returns:
            Dictionary with form metrics:
            {
                'games_played': 5,
                'points': 10,
                'points_per_game': 2.0,
                'wins': 3,
                'draws': 1,
                'losses': 1,
                'win_rate': 0.6,
                'goals_for': 8,
                'goals_against': 4,
                'goals_for_per_game': 1.6,
                'goals_against_per_game': 0.8,
                'goal_difference': 4,
                'weighted_points': 9.5,  # Recent games weighted higher
                'form_string': 'WWDLW',  # Last 5 results
                'momentum': 'positive',  # or 'negative' or 'neutral'
                'clean_sheets': 2,
                'failed_to_score': 0
            }
        """
        # Get recent matches
        matches = self.get_recent_matches(
            team_id=team_id,
            before_date=before_date,
            is_home=is_home,
            limit=self.lookback_games
        )
        
        # If not enough matches, return empty form
        if not matches:
            logger.warning(f"No matches found for team {team_id}")
            return self._empty_form()
        
        # Calculate weights for exponential decay
        weights = self.calculate_exponential_weights(len(matches))
        
        # Initialise counters
        points = 0
        weighted_points = 0.0
        wins = draws = losses = 0
        goals_for = goals_against = 0
        clean_sheets = failed_to_score = 0
        form_string = ""
        
        # Process each match
        for i, match in enumerate(matches):
            result, gf, ga, pts = self.calculate_match_result(match, team_id)
            
            # Accumulate stats
            points += pts
            weighted_points += pts * weights[i]
            
            if result == 'W':
                wins += 1
            elif result == 'D':
                draws += 1
            else:
                losses += 1
            
            goals_for += gf
            goals_against += ga
            
            if ga == 0:
                clean_sheets += 1
            if gf == 0:
                failed_to_score += 1
            
            # Build form string (most recent first)
            form_string += result
        
        # Calculate averages
        games_played = len(matches)
        points_per_game = points / games_played if games_played > 0 else 0.0
        goals_for_per_game = goals_for / games_played if games_played > 0 else 0.0
        goals_against_per_game = goals_against / games_played if games_played > 0 else 0.0
        win_rate = wins / games_played if games_played > 0 else 0.0
        
        # Calculate momentum (are we getting better or worse?)
        # Compare first half of period to second half
        momentum = self._calculate_momentum(matches, team_id)
        
        return {
            'games_played': games_played,
            'points': points,
            'points_per_game': points_per_game,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'win_rate': win_rate,
            'goals_for': goals_for,
            'goals_against': goals_against,
            'goals_for_per_game': goals_for_per_game,
            'goals_against_per_game': goals_against_per_game,
            'goal_difference': goals_for - goals_against,
            'weighted_points': weighted_points,
            'form_string': form_string,
            'momentum': momentum,
            'clean_sheets': clean_sheets,
            'failed_to_score': failed_to_score
        }
    
    def _calculate_momentum(
        self,
        matches: List[Match],
        team_id: int
    ) -> str:
        """
        Detect if team is on upward or downward trend.
        
        Compares recent half to older half. If recent performance better
        than older performance, momentum is positive (team improving).
        
        Args:
            matches: List of matches (newest first)
            team_id: Team to analyse
            
        Returns:
            'positive', 'negative', or 'neutral'
        """
        if len(matches) < 4:
            return 'neutral'  # Need at least 4 games to detect trend
        
        # Split into recent half and older half
        mid = len(matches) // 2
        recent_matches = matches[:mid]
        older_matches = matches[mid:]
        
        # Calculate points in each period
        recent_points = sum(
            self.calculate_match_result(m, team_id)[3]
            for m in recent_matches
        )
        older_points = sum(
            self.calculate_match_result(m, team_id)[3]
            for m in older_matches
        )
        
        # Calculate points per game for fair comparison
        recent_ppg = recent_points / len(recent_matches)
        older_ppg = older_points / len(older_matches)
        
        # Determine momentum (need >0.5 ppg difference to be significant)
        if recent_ppg > older_ppg + 0.5:
            return 'positive'
        elif recent_ppg < older_ppg - 0.5:
            return 'negative'
        else:
            return 'neutral'
    
    def _empty_form(self) -> Dict:
        """Return empty form dict when no data available."""
        return {
            'games_played': 0,
            'points': 0,
            'points_per_game': 0.0,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'win_rate': 0.0,
            'goals_for': 0,
            'goals_against': 0,
            'goals_for_per_game': 0.0,
            'goals_against_per_game': 0.0,
            'goal_difference': 0,
            'weighted_points': 0.0,
            'form_string': '',
            'momentum': 'neutral',
            'clean_sheets': 0,
            'failed_to_score': 0
        }
    
    def calculate_match_form_features(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate form features for both teams in an upcoming match.
        
        This is what you'd use when preparing to predict a match.
        Gets form for both teams and calculates differentials.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date of match (for backtesting, else None = now)
            
        Returns:
            Dictionary with features for both teams plus differentials:
            {
                'home_form': {...},  # All home team form metrics
                'away_form': {...},  # All away team form metrics
                'home_away_form': {...},  # Home team's home-only form
                'away_away_form': {...},  # Away team's away-only form
                'form_differential': 1.2,  # Home ppg - Away ppg
                'momentum_differential': 1,  # +1 if home better, -1 if away better
                ...
            }
        """
        # Get overall form for both teams
        home_form_all = self.calculate_team_form(
            team_id=home_team_id,
            before_date=match_date,
            is_home=None  # All matches
        )
        
        away_form_all = self.calculate_team_form(
            team_id=away_team_id,
            before_date=match_date,
            is_home=None  # All matches
        )
        
        # Get venue-specific form if enabled
        if self.home_away_split:
            home_form_venue = self.calculate_team_form(
                team_id=home_team_id,
                before_date=match_date,
                is_home=True  # Home matches only
            )
            
            away_form_venue = self.calculate_team_form(
                team_id=away_team_id,
                before_date=match_date,
                is_home=False  # Away matches only
            )
        else:
            home_form_venue = home_form_all
            away_form_venue = away_form_all
        
        # Calculate differentials (how much better is home team's form?)
        form_differential = (
            home_form_venue['points_per_game'] - 
            away_form_venue['points_per_game']
        )
        
        # Momentum differential (+1 if home improving, -1 if away improving)
        momentum_map = {'positive': 1, 'neutral': 0, 'negative': -1}
        momentum_differential = (
            momentum_map[home_form_venue['momentum']] -
            momentum_map[away_form_venue['momentum']]
        )
        
        # Goals differential
        goals_for_differential = (
            home_form_venue['goals_for_per_game'] -
            away_form_venue['goals_for_per_game']
        )
        
        goals_against_differential = (
            home_form_venue['goals_against_per_game'] -
            away_form_venue['goals_against_per_game']
        )
        
        return {
            'home_form_all': home_form_all,
            'away_form_all': away_form_all,
            'home_form_venue': home_form_venue,
            'away_form_venue': away_form_venue,
            'form_differential': form_differential,
            'momentum_differential': momentum_differential,
            'goals_for_differential': goals_for_differential,
            'goals_against_differential': goals_against_differential,
            'home_form_string': home_form_venue['form_string'],
            'away_form_string': away_form_venue['form_string']
        }
    
    def get_form_summary(
        self,
        team_id: int,
        is_home: Optional[bool] = None
    ) -> str:
        """
        Get human-readable form summary for a team.
        
        Args:
            team_id: Team to summarise
            is_home: Home form (True), away form (False), or overall (None)
            
        Returns:
            String like "WWDLW (10 pts, +4 GD, positive momentum)"
        """
        form = self.calculate_team_form(team_id=team_id, is_home=is_home)
        
        return (
            f"{form['form_string']} "
            f"({form['points']} pts, "
            f"{form['goal_difference']:+d} GD, "
            f"{form['momentum']} momentum)"
        )


# Convenience function for quick form checks
def get_team_form_string(team_id: int, num_games: int = 5) -> str:
    """
    Quick function to get team's recent form string.
    
    Args:
        team_id: Team to check
        num_games: How many games back (default 5)
        
    Returns:
        Form string like "WWDLW"
        
    Example:
        >>> get_team_form_string(team_id=1)
        'WWDLW'
    """
    calc = FormCalculator(lookback_games=num_games)
    form = calc.calculate_team_form(team_id=team_id)
    return form['form_string']


if __name__ == '__main__':
    """
    Quick test to verify form calculator works.
    Run: python -m src.features.form_calculator
    """
    print("Form Calculator Test\n")
    
    from data.database import Session, Team
    
    session = Session()
    
    # Get a team to test
    team = session.query(Team).first()
    
    if team:
        print(f"Testing form for: {team.name}\n")
        
        calc = FormCalculator(lookback_games=5, exponential_decay=0.9)
        
        # Overall form
        form = calc.calculate_team_form(team_id=team.id)
        print(f"Overall Form: {form['form_string']}")
        print(f"Points: {form['points']}/15")
        print(f"PPG: {form['points_per_game']:.2f}")
        print(f"Goals: {form['goals_for']}-{form['goals_against']}")
        print(f"Momentum: {form['momentum']}")
        
        # Home form
        print("\nHome Form:")
        home_form = calc.calculate_team_form(team_id=team.id, is_home=True)
        print(f"  {home_form['form_string']} ({home_form['points']} pts)")
        
        # Away form
        print("\nAway Form:")
        away_form = calc.calculate_team_form(team_id=team.id, is_home=False)
        print(f"  {away_form['form_string']} ({away_form['points']} pts)")
        
    else:
        print("No teams in database")
    
    session.close()
    
    print("\nForm Calculator working correctly")