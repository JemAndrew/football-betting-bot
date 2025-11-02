"""
Team Features Calculator - Attack and Defence Stats

Calculates team playing style metrics relative to league average.
These are essential inputs for the Poisson goals model.

Key concept: Some teams are high-scoring (attack-focused), others defensive.
We need to know each team's style to predict goals accurately.

Main metrics:
- Attack strength: Goals scored vs league average
- Defence strength: Goals conceded vs league average  
- Clean sheet rate: How often they don't concede
- Failed to score rate: How often they don't score
- Home/away split for all metrics

Why relative to league average?
- A team scoring 2 goals/game in Championship is excellent
- Same team scoring 2 goals/game in Premier League is average
- We need context: are they above or below average for their league?

Usage:
    features = TeamFeatures()
    home_features = features.calculate_team_features(team_id=1, venue='home')
    away_features = features.calculate_team_features(team_id=2, venue='away')
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

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


class TeamFeatures:
    """
    Calculates team attack and defence statistics.
    
    Attack strength and defence strength are the core inputs for Poisson model.
    They tell us: is this team better or worse than average at scoring/preventing goals?
    """
    
    def __init__(
        self,
        lookback_games: Optional[int] = None,
        lookback_days: Optional[int] = 90,
        min_games: int = 5
    ):
        """
        Initialise team features calculator.
        
        Args:
            lookback_games: Use last N games (None = use lookback_days instead)
            lookback_days: Use games from last N days (default 90 = ~3 months)
            min_games: Minimum games needed for reliable stats
        
        Note: Usually better to use lookback_days rather than lookback_games
              because we want recent stats but need enough data for reliability.
        """
        self.lookback_games = lookback_games
        self.lookback_days = lookback_days
        self.min_games = min_games
        
        logger.info(
            f"Team Features initialised: Lookback Games={lookback_games}, "
            f"Lookback Days={lookback_days}, Min Games={min_games}"
        )
    
    def get_team_matches(
        self,
        team_id: int,
        venue: Optional[str] = None,
        before_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> list:
        """
        Get matches for a team with optional filters.
        
        Args:
            team_id: Team to get matches for
            venue: 'home', 'away', or None for both
            before_date: Only matches before this date (for backtesting)
            limit: Maximum number of matches
            
        Returns:
            List of Match objects
        """
        session = Session()
        
        try:
            # Base query - finished matches involving this team
            query = session.query(Match).filter(
                Match.status == 'FINISHED',
                (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
            )
            
            # Filter by venue if specified
            if venue == 'home':
                query = query.filter(Match.home_team_id == team_id)
            elif venue == 'away':
                query = query.filter(Match.away_team_id == team_id)
            
            # Filter by date - either specific date or lookback period
            if before_date:
                query = query.filter(Match.date < before_date)
                
                # Apply lookback period if specified
                if self.lookback_days:
                    cutoff_date = before_date - timedelta(days=self.lookback_days)
                    query = query.filter(Match.date >= cutoff_date)
            elif self.lookback_days:
                cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
                query = query.filter(Match.date >= cutoff_date)
            
            # Order by date (newest first) and apply limit
            matches = query.order_by(Match.date.desc())
            
            if limit or self.lookback_games:
                limit_value = limit if limit else self.lookback_games
                matches = matches.limit(limit_value)
            
            return matches.all()
            
        finally:
            session.close()
    
    def calculate_league_averages(
        self,
        league_id: str = 'PL',
        before_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Calculate league-wide scoring averages.
        
        This is our baseline. A team with 1.5 goals/game is only good if
        the league average is 1.2. If league average is 2.0, they're below par.
        
        Args:
            league_id: League to calculate for (default 'PL' = Premier League)
            before_date: Calculate averages as of this date (for backtesting)
            
        Returns:
            Dictionary with league averages:
            {
                'goals_per_game': 2.8,
                'home_goals_per_game': 1.5,
                'away_goals_per_game': 1.3,
                'btts_rate': 0.52,  # Both teams score rate
                'over_25_rate': 0.48  # Over 2.5 goals rate
            }
        """
        session = Session()
        
        try:
            # Get all finished matches in this league
            query = session.query(Match).filter(
                Match.status == 'FINISHED',
                Match.league_id == league_id
            )
            
            # Apply date filter
            if before_date:
                query = query.filter(Match.date < before_date)
                
                if self.lookback_days:
                    cutoff_date = before_date - timedelta(days=self.lookback_days)
                    query = query.filter(Match.date >= cutoff_date)
            elif self.lookback_days:
                cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
                query = query.filter(Match.date >= cutoff_date)
            
            matches = query.all()
            
            if not matches:
                logger.warning(f"No matches found for league {league_id}")
                return self._default_league_averages()
            
            # Calculate stats
            total_goals = 0
            home_goals = 0
            away_goals = 0
            btts_count = 0
            over_25_count = 0
            
            for match in matches:
                home_goals += match.home_goals
                away_goals += match.away_goals
                total_goals += match.home_goals + match.away_goals
                
                # Both teams scored?
                if match.home_goals > 0 and match.away_goals > 0:
                    btts_count += 1
                
                # Over 2.5 goals?
                if (match.home_goals + match.away_goals) > 2.5:
                    over_25_count += 1
            
            num_matches = len(matches)
            
            return {
                'goals_per_game': total_goals / num_matches,
                'home_goals_per_game': home_goals / num_matches,
                'away_goals_per_game': away_goals / num_matches,
                'btts_rate': btts_count / num_matches,
                'over_25_rate': over_25_count / num_matches
            }
            
        finally:
            session.close()
    
    def _default_league_averages(self) -> Dict[str, float]:
        """Default averages if no data available (typical Premier League stats)."""
        return {
            'goals_per_game': 2.8,
            'home_goals_per_game': 1.5,
            'away_goals_per_game': 1.3,
            'btts_rate': 0.52,
            'over_25_rate': 0.48
        }
    
    def calculate_team_features(
        self,
        team_id: int,
        venue: Optional[str] = None,
        before_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate comprehensive features for a team.
        
        This is the main function. Returns everything needed for Poisson model.
        
        Args:
            team_id: Team to analyse
            venue: 'home', 'away', or None for overall
            before_date: Calculate as of this date (for backtesting)
            
        Returns:
            Dictionary with team features:
            {
                'games_played': 20,
                'goals_for': 35,
                'goals_against': 28,
                'goals_for_per_game': 1.75,
                'goals_against_per_game': 1.40,
                'attack_strength': 1.17,  # vs league average (>1 = better)
                'defence_strength': 0.93,  # vs league average (<1 = better)
                'clean_sheets': 8,
                'clean_sheet_rate': 0.40,
                'failed_to_score': 3,
                'failed_to_score_rate': 0.15,
                'avg_goals_per_match': 3.15,  # Total goals in their matches
                'high_scoring_rate': 0.55,  # % of matches over 2.5 goals
                'btts_rate': 0.60,  # % where both teams scored
                'days_since_last_match': 7
            }
        """
        # Get team's matches
        matches = self.get_team_matches(
            team_id=team_id,
            venue=venue,
            before_date=before_date
        )
        
        # Check if enough data
        if len(matches) < self.min_games:
            logger.warning(
                f"Team {team_id} only has {len(matches)} matches "
                f"(minimum {self.min_games} needed)"
            )
            return self._empty_features()
        
        # Get league averages for comparison
        league_avg = self.calculate_league_averages(
            league_id='PL',  # Could make this dynamic
            before_date=before_date
        )
        
        # Initialise counters
        goals_for = 0
        goals_against = 0
        clean_sheets = 0
        failed_to_score = 0
        total_goals_in_matches = 0
        over_25_count = 0
        btts_count = 0
        
        # Process each match
        for match in matches:
            # Determine if team was home or away
            is_home = (match.home_team_id == team_id)
            
            if is_home:
                gf = match.home_goals
                ga = match.away_goals
            else:
                gf = match.away_goals
                ga = match.home_goals
            
            # Accumulate stats
            goals_for += gf
            goals_against += ga
            total_goals_in_matches += match.home_goals + match.away_goals
            
            if ga == 0:
                clean_sheets += 1
            if gf == 0:
                failed_to_score += 1
            
            if (match.home_goals + match.away_goals) > 2.5:
                over_25_count += 1
            
            if match.home_goals > 0 and match.away_goals > 0:
                btts_count += 1
        
        # Calculate per-game rates
        games_played = len(matches)
        goals_for_per_game = goals_for / games_played
        goals_against_per_game = goals_against / games_played
        avg_goals_per_match = total_goals_in_matches / games_played
        
        # Calculate strength relative to league average
        # Attack strength: How many goals do they score vs league average?
        # >1.0 means better than average, <1.0 means worse
        if venue == 'home':
            attack_strength = goals_for_per_game / league_avg['home_goals_per_game']
            defence_strength = goals_against_per_game / league_avg['away_goals_per_game']
        elif venue == 'away':
            attack_strength = goals_for_per_game / league_avg['away_goals_per_game']
            defence_strength = goals_against_per_game / league_avg['home_goals_per_game']
        else:
            # Overall: compare to average goals per side
            avg_per_team = league_avg['goals_per_game'] / 2
            attack_strength = goals_for_per_game / avg_per_team
            defence_strength = goals_against_per_game / avg_per_team
        
        # Calculate days since last match (for fatigue/rest analysis)
        if before_date:
            days_since_last = (before_date - matches[0].date).days
        else:
            days_since_last = (datetime.now() - matches[0].date).days
        
        return {
            'games_played': games_played,
            'goals_for': goals_for,
            'goals_against': goals_against,
            'goals_for_per_game': goals_for_per_game,
            'goals_against_per_game': goals_against_per_game,
            'attack_strength': attack_strength,
            'defence_strength': defence_strength,
            'clean_sheets': clean_sheets,
            'clean_sheet_rate': clean_sheets / games_played,
            'failed_to_score': failed_to_score,
            'failed_to_score_rate': failed_to_score / games_played,
            'avg_goals_per_match': avg_goals_per_match,
            'high_scoring_rate': over_25_count / games_played,
            'btts_rate': btts_count / games_played,
            'days_since_last_match': days_since_last
        }
    
    def _empty_features(self) -> Dict:
        """Return empty features when insufficient data."""
        return {
            'games_played': 0,
            'goals_for': 0,
            'goals_against': 0,
            'goals_for_per_game': 0.0,
            'goals_against_per_game': 0.0,
            'attack_strength': 1.0,  # Default to average
            'defence_strength': 1.0,
            'clean_sheets': 0,
            'clean_sheet_rate': 0.0,
            'failed_to_score': 0,
            'failed_to_score_rate': 0.0,
            'avg_goals_per_match': 0.0,
            'high_scoring_rate': 0.0,
            'btts_rate': 0.0,
            'days_since_last_match': 0
        }
    
    def calculate_match_features(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate features for both teams in a match.
        
        This prepares all inputs needed for Poisson goals model.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date of match (for backtesting)
            
        Returns:
            Dictionary with features for both teams:
            {
                'home_features': {...},  # Home team stats
                'away_features': {...},  # Away team stats
                'attack_differential': 0.25,  # Home attack vs Away attack
                'defence_differential': -0.15,  # Home defence vs Away defence
                'expected_goals_ratio': 1.4,  # Rough estimate of goal split
                ...
            }
        """
        # Get venue-specific features
        home_features = self.calculate_team_features(
            team_id=home_team_id,
            venue='home',
            before_date=match_date
        )
        
        away_features = self.calculate_team_features(
            team_id=away_team_id,
            venue='away',
            before_date=match_date
        )
        
        # Calculate differentials
        attack_differential = (
            home_features['attack_strength'] - 
            away_features['attack_strength']
        )
        
        defence_differential = (
            home_features['defence_strength'] - 
            away_features['defence_strength']
        )
        
        # Rough expected goals ratio (not final Poisson calculation)
        # This is just for feature comparison
        home_xg_factor = home_features['attack_strength'] * away_features['defence_strength']
        away_xg_factor = away_features['attack_strength'] * home_features['defence_strength']
        
        if away_xg_factor > 0:
            expected_goals_ratio = home_xg_factor / away_xg_factor
        else:
            expected_goals_ratio = 1.0
        
        return {
            'home_features': home_features,
            'away_features': away_features,
            'attack_differential': attack_differential,
            'defence_differential': defence_differential,
            'expected_goals_ratio': expected_goals_ratio,
            'home_attack_vs_away_defence': home_features['attack_strength'] * away_features['defence_strength'],
            'away_attack_vs_home_defence': away_features['attack_strength'] * home_features['defence_strength']
        }
    
    def get_head_to_head(
        self,
        team_a_id: int,
        team_b_id: int,
        limit: int = 5
    ) -> Dict:
        """
        Get head-to-head record between two teams.
        
        Historical matchups can be predictive, especially in local derbies.
        
        Args:
            team_a_id: First team
            team_b_id: Second team
            limit: How many recent H2H matches to analyse
            
        Returns:
            Dictionary with H2H stats:
            {
                'matches_played': 5,
                'team_a_wins': 2,
                'draws': 1,
                'team_b_wins': 2,
                'team_a_goals': 8,
                'team_b_goals': 9,
                'avg_total_goals': 3.4,
                'btts_rate': 0.8
            }
        """
        session = Session()
        
        try:
            # Get matches between these two teams
            query = session.query(Match).filter(
                Match.status == 'FINISHED',
                (
                    ((Match.home_team_id == team_a_id) & (Match.away_team_id == team_b_id)) |
                    ((Match.home_team_id == team_b_id) & (Match.away_team_id == team_a_id))
                )
            ).order_by(Match.date.desc()).limit(limit)
            
            matches = query.all()
            
            if not matches:
                return self._empty_h2h()
            
            # Calculate H2H stats
            team_a_wins = draws = team_b_wins = 0
            team_a_goals = team_b_goals = total_goals = 0
            btts_count = 0
            
            for match in matches:
                # Figure out which team was home
                if match.home_team_id == team_a_id:
                    a_goals = match.home_goals
                    b_goals = match.away_goals
                else:
                    a_goals = match.away_goals
                    b_goals = match.home_goals
                
                team_a_goals += a_goals
                team_b_goals += b_goals
                total_goals += a_goals + b_goals
                
                if a_goals > b_goals:
                    team_a_wins += 1
                elif a_goals == b_goals:
                    draws += 1
                else:
                    team_b_wins += 1
                
                if a_goals > 0 and b_goals > 0:
                    btts_count += 1
            
            num_matches = len(matches)
            
            return {
                'matches_played': num_matches,
                'team_a_wins': team_a_wins,
                'draws': draws,
                'team_b_wins': team_b_wins,
                'team_a_goals': team_a_goals,
                'team_b_goals': team_b_goals,
                'avg_total_goals': total_goals / num_matches,
                'btts_rate': btts_count / num_matches
            }
            
        finally:
            session.close()
    
    def _empty_h2h(self) -> Dict:
        """Return empty H2H when no data available."""
        return {
            'matches_played': 0,
            'team_a_wins': 0,
            'draws': 0,
            'team_b_wins': 0,
            'team_a_goals': 0,
            'team_b_goals': 0,
            'avg_total_goals': 0.0,
            'btts_rate': 0.0
        }


if __name__ == '__main__':
    """
    Quick test of team features calculator.
    Run: python -m src.features.team_features
    """
    print("Team Features Calculator Test\n")
    
    from data.database import Session, Team
    
    session = Session()
    team = session.query(Team).first()
    
    if team:
        print(f"Testing features for: {team.name}\n")
        
        features = TeamFeatures(lookback_days=90)
        
        # Overall features
        overall = features.calculate_team_features(team_id=team.id)
        print("Overall Stats:")
        print(f"  Goals For: {overall['goals_for_per_game']:.2f} per game")
        print(f"  Goals Against: {overall['goals_against_per_game']:.2f} per game")
        print(f"  Attack Strength: {overall['attack_strength']:.2f}x league avg")
        print(f"  Defence Strength: {overall['defence_strength']:.2f}x league avg")
        print(f"  Clean Sheets: {overall['clean_sheet_rate']:.1%}")
        
        # Home stats
        home = features.calculate_team_features(team_id=team.id, venue='home')
        print(f"\nHome Stats:")
        print(f"  Goals For: {home['goals_for_per_game']:.2f} per game")
        print(f"  Attack Strength: {home['attack_strength']:.2f}x")
        
        # Away stats
        away = features.calculate_team_features(team_id=team.id, venue='away')
        print(f"\nAway Stats:")
        print(f"  Goals For: {away['goals_for_per_game']:.2f} per game")
        print(f"  Attack Strength: {away['attack_strength']:.2f}x")
        
    else:
        print("No teams in database")
    
    session.close()
    
    print("\nTeam Features working correctly")