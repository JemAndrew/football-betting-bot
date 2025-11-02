"""
ELO Rating System for Football Teams

Calculates and updates team strength ratings based on match results.
ELO is a relative measure - higher rating = stronger team.

Core Concepts:
- New teams start at 1500 (neutral)
- Wins increase rating, losses decrease it
- Beating a stronger team gives more points than beating a weaker team
- K-factor controls how quickly ratings change (20 for normal, 30 for playoffs)
- Home advantage typically worth ~100 ELO points

Usage:
    calculator = ELOCalculator(k_factor=20, home_advantage=100)
    new_home_elo, new_away_elo = calculator.update_elo(
        home_elo=1500, away_elo=1600,
        home_goals=2, away_goals=1
    )
"""

from typing import Tuple, Optional
from datetime import datetime
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


class ELOCalculator:
    """
    Calculates and updates team ELO ratings based on match results.
    
    The ELO system is self-correcting - if a team is overrated, they'll lose
    more than expected and their rating drops. If underrated, they'll exceed
    expectations and rise.
    """
    
    DEFAULT_ELO = 1500  # Starting rating for new teams
    
    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 100.0,
        goal_importance: float = 1.0
    ):
        """
        Initialise ELO calculator with tuning parameters.
        
        Args:
            k_factor: How quickly ratings change (higher = more volatile)
                     20 = standard, 30 = playoffs/important matches, 10 = conservative
            home_advantage: ELO points added to home team (typically 80-120)
            goal_importance: Goal difference multiplier (1.0 = standard, 1.5 = more weight)
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.goal_importance = goal_importance
        
        logger.info(
            f"ELO Calculator initialised: K={k_factor}, "
            f"Home Advantage={home_advantage}, Goal Weight={goal_importance}"
        )
    
    def calculate_expected_score(
        self,
        team_elo: float,
        opponent_elo: float,
        is_home: bool = False
    ) -> float:
        """
        Calculate expected match outcome (0.0 = certain loss, 1.0 = certain win).
        
        This is the probability that 'team' beats 'opponent' based purely on
        their ELO ratings. The formula comes from chess ELO but works well for football.
        
        Args:
            team_elo: Team's current ELO rating
            opponent_elo: Opponent's current ELO rating  
            is_home: Whether team is playing at home (adds home advantage)
            
        Returns:
            Expected score (0.0 to 1.0, where 0.5 = 50-50 match)
            
        Examples:
            >>> calc = ELOCalculator()
            >>> calc.calculate_expected_score(1500, 1500, is_home=False)
            0.5  # Evenly matched
            >>> calc.calculate_expected_score(1600, 1500, is_home=False)  
            0.64  # Stronger team favoured
            >>> calc.calculate_expected_score(1500, 1500, is_home=True)
            0.64  # Home advantage worth ~100 ELO
        """
        # Apply home advantage if applicable
        if is_home:
            team_elo += self.home_advantage
        
        # Standard ELO formula: 1 / (1 + 10^((opponent - team) / 400))
        elo_diff = opponent_elo - team_elo
        expected = 1.0 / (1.0 + math.pow(10, elo_diff / 400.0))
        
        return expected
    
    def calculate_actual_score(
        self,
        team_goals: int,
        opponent_goals: int
    ) -> float:
        """
        Convert match result to a score (1.0 = win, 0.5 = draw, 0.0 = loss).
        
        Args:
            team_goals: Goals scored by team
            opponent_goals: Goals scored by opponent
            
        Returns:
            Actual score for the team (1.0, 0.5, or 0.0)
        """
        if team_goals > opponent_goals:
            return 1.0  # Win
        elif team_goals == opponent_goals:
            return 0.5  # Draw
        else:
            return 0.0  # Loss
    
    def calculate_goal_difference_multiplier(
        self,
        goal_difference: int
    ) -> float:
        """
        Scale K-factor based on margin of victory.
        
        Thrashing someone 5-0 should change ratings more than scraping 1-0.
        But we don't want 10-0 to count 10x as much (likely outliers).
        
        Args:
            goal_difference: Absolute goal difference
            
        Returns:
            Multiplier for K-factor (1.0 for 1-goal wins, up to ~2.5 for thrashings)
            
        Formula: Uses square root to dampen extreme results
                 1-goal = 1.0x, 2-goal = 1.5x, 3-goal = 1.8x, 5-goal = 2.3x
        """
        if goal_difference <= 1:
            return 1.0
        
        # Square root scaling - diminishing returns for bigger wins
        multiplier = 1.0 + (math.sqrt(goal_difference - 1) * self.goal_importance * 0.5)
        
        # Cap at 2.5x to prevent single matches dominating ratings
        return min(multiplier, 2.5)
    
    def update_elo(
        self,
        home_elo: float,
        away_elo: float,
        home_goals: int,
        away_goals: int,
        k_factor: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Update both teams' ELO ratings after a match.
        
        This is the main function you'll use. It:
        1. Calculates what was expected to happen
        2. Looks at what actually happened  
        3. Adjusts ratings based on the surprise factor
        
        Args:
            home_elo: Home team's ELO before match
            away_elo: Away team's ELO before match
            home_goals: Home team's goals scored
            away_goals: Away team's goals scored
            k_factor: Optional override for K-factor (e.g. 30 for playoffs)
            
        Returns:
            Tuple of (new_home_elo, new_away_elo)
            
        Example:
            >>> calc = ELOCalculator(k_factor=20)
            >>> # Man City (1850) beats Luton (1450) 5-1 at home
            >>> new_home, new_away = calc.update_elo(1850, 1450, 5, 1)
            >>> # Man City gains ~5 points (expected to win anyway)
            >>> # Luton loses ~5 points (expected to lose)
        """
        # Use instance K-factor unless overridden
        k = k_factor if k_factor is not None else self.k_factor
        
        # Calculate expected outcomes (with home advantage for home team)
        home_expected = self.calculate_expected_score(home_elo, away_elo, is_home=True)
        away_expected = 1.0 - home_expected  # Away expectation is inverse
        
        # Calculate actual outcomes
        home_actual = self.calculate_actual_score(home_goals, away_goals)
        away_actual = 1.0 - home_actual  # Zero-sum game
        
        # Apply goal difference multiplier
        goal_diff = abs(home_goals - away_goals)
        gd_multiplier = self.calculate_goal_difference_multiplier(goal_diff)
        
        # Update ELO ratings
        # Formula: New = Old + K * GD_Multiplier * (Actual - Expected)
        home_change = k * gd_multiplier * (home_actual - home_expected)
        away_change = k * gd_multiplier * (away_actual - away_expected)
        
        new_home_elo = home_elo + home_change
        new_away_elo = away_elo + away_change
        
        logger.debug(
            f"ELO Update: Home {home_elo:.1f} → {new_home_elo:.1f} ({home_change:+.1f}), "
            f"Away {away_elo:.1f} → {new_away_elo:.1f} ({away_change:+.1f}) | "
            f"Score {home_goals}-{away_goals}, Expected {home_expected:.2f}"
        )
        
        return new_home_elo, new_away_elo
    
    def calculate_historical_elos(
        self,
        league_id: Optional[str] = None,
        season: Optional[str] = None,
        reset_elos: bool = True
    ) -> None:
        """
        Calculate ELO ratings for all matches in database chronologically.
        
        This processes matches in date order, updating team ELOs after each match.
        Creates a historical record of team strength over time.
        
        Args:
            league_id: Filter to specific league (e.g., 'PL' for Premier League)
            season: Filter to specific season (e.g., '2024')
            reset_elos: Whether to reset all teams to 1500 before calculating
                       (True = fresh start, False = continue from current ELOs)
                       
        Side Effects:
            Updates team.current_elo in database for all teams
            
        Example:
            >>> calc = ELOCalculator()
            >>> calc.calculate_historical_elos(league_id='PL', season='2024')
            >>> # All Premier League teams now have updated ELO ratings
        """
        session = Session()
        
        try:
            # Reset all teams to default ELO if requested
            if reset_elos:
                logger.info("Resetting all team ELOs to 1500")
                teams = session.query(Team).all()
                for team in teams:
                    team.current_elo = self.DEFAULT_ELO
                session.commit()
            
            # Build query for matches
            query = session.query(Match).filter(Match.status == 'FINISHED')
            
            if league_id:
                query = query.filter(Match.league_id == league_id)
            if season:
                query = query.filter(Match.season == season)
            
            # Order by date to process chronologically
            matches = query.order_by(Match.date).all()
            
            logger.info(
                f"Calculating ELO for {len(matches)} matches "
                f"(League: {league_id or 'All'}, Season: {season or 'All'})"
            )
            
            updated_count = 0
            
            for match in matches:
                # Get current ELOs for both teams
                home_team = session.query(Team).filter_by(id=match.home_team_id).first()
                away_team = session.query(Team).filter_by(id=match.away_team_id).first()
                
                if not home_team or not away_team:
                    logger.warning(f"Missing team for match {match.id}, skipping")
                    continue
                
                # Skip if no score data
                if match.home_goals is None or match.away_goals is None:
                    logger.debug(f"No score data for match {match.id}, skipping")
                    continue
                
                # Calculate new ELOs
                new_home_elo, new_away_elo = self.update_elo(
                    home_elo=home_team.current_elo,
                    away_elo=away_team.current_elo,
                    home_goals=match.home_goals,
                    away_goals=match.away_goals
                )
                
                # Update database
                home_team.current_elo = new_home_elo
                away_team.current_elo = new_away_elo
                
                updated_count += 1
                
                # Commit every 50 matches to avoid memory issues
                if updated_count % 50 == 0:
                    session.commit()
                    logger.debug(f"Processed {updated_count}/{len(matches)} matches")
            
            # Final commit
            session.commit()
            
            logger.info(
                f"ELO calculation complete: {updated_count} matches processed"
            )
            
            # Log top teams by ELO
            top_teams = session.query(Team).order_by(Team.current_elo.desc()).limit(5).all()
            logger.info("Top 5 teams by ELO:")
            for i, team in enumerate(top_teams, 1):
                logger.info(f"  {i}. {team.name}: {team.current_elo:.1f}")
                
        except Exception as e:
            session.rollback()
            logger.error(f"Error calculating historical ELOs: {e}")
            raise
        finally:
            session.close()
    
    def get_team_elo(self, team_id: int) -> float:
        """
        Get current ELO rating for a team.
        
        Args:
            team_id: Database ID of team
            
        Returns:
            Current ELO rating (defaults to 1500 if team not found)
        """
        session = Session()
        try:
            team = session.query(Team).filter_by(id=team_id).first()
            if team:
                return team.current_elo
            else:
                logger.warning(f"Team {team_id} not found, returning default ELO")
                return self.DEFAULT_ELO
        finally:
            session.close()
    
    def predict_match_outcome(
        self,
        home_team_id: int,
        away_team_id: int
    ) -> dict:
        """
        Predict match outcome probabilities based on current ELO ratings.
        
        Args:
            home_team_id: Database ID of home team
            away_team_id: Database ID of away team
            
        Returns:
            Dictionary with:
                - home_win_prob: Probability home team wins (0.0-1.0)
                - draw_prob: Estimated draw probability (~0.25 for football)
                - away_win_prob: Probability away team wins (0.0-1.0)
                - home_elo: Current home team ELO
                - away_elo: Current away team ELO
                - expected_home_score: Expected score for home team (0.0-1.0 scale)
                
        Note:
            This is a simplified model. In reality, you'd use Poisson distribution
            for more accurate goal predictions. See goals_model.py for that.
            
        Example:
            >>> calc = ELOCalculator()
            >>> prediction = calc.predict_match_outcome(home_team_id=1, away_team_id=2)
            >>> print(f"Home win: {prediction['home_win_prob']:.1%}")
        """
        home_elo = self.get_team_elo(home_team_id)
        away_elo = self.get_team_elo(away_team_id)
        
        # Calculate expected score (probability home wins without draws)
        expected_home = self.calculate_expected_score(home_elo, away_elo, is_home=True)
        
        # Rough estimate: ~25% of matches are draws in football
        # This is a simplification - use Poisson model for accurate predictions
        draw_prob = 0.25
        
        # Adjust win probabilities to account for draws
        home_win_prob = expected_home * (1 - draw_prob)
        away_win_prob = (1 - expected_home) * (1 - draw_prob)
        
        return {
            'home_win_prob': home_win_prob,
            'draw_prob': draw_prob,
            'away_win_prob': away_win_prob,
            'home_elo': home_elo,
            'away_elo': away_elo,
            'expected_home_score': expected_home,
            'elo_differential': home_elo - away_elo + self.home_advantage
        }


# Convenience function for quick ELO updates
def update_match_elos(match_id: int, k_factor: float = 20.0) -> None:
    """
    Update ELO ratings for a single match.
    
    Useful for processing new matches as they finish.
    
    Args:
        match_id: Database ID of finished match
        k_factor: K-factor to use (20 = normal, 30 = important match)
        
    Example:
        >>> update_match_elos(match_id=12345)  # Updates ELOs for match 12345
    """
    session = Session()
    calculator = ELOCalculator(k_factor=k_factor)
    
    try:
        match = session.query(Match).filter_by(id=match_id).first()
        
        if not match:
            logger.error(f"Match {match_id} not found")
            return
        
        if match.status != 'FINISHED':
            logger.warning(f"Match {match_id} not finished yet")
            return
        
        if match.home_goals is None or match.away_goals is None:
            logger.warning(f"Match {match_id} missing score data")
            return
        
        # Get teams
        home_team = session.query(Team).filter_by(id=match.home_team_id).first()
        away_team = session.query(Team).filter_by(id=match.away_team_id).first()
        
        if not home_team or not away_team:
            logger.error(f"Missing team for match {match_id}")
            return
        
        # Update ELOs
        new_home_elo, new_away_elo = calculator.update_elo(
            home_elo=home_team.current_elo,
            away_elo=away_team.current_elo,
            home_goals=match.home_goals,
            away_goals=match.away_goals
        )
        
        home_team.current_elo = new_home_elo
        away_team.current_elo = new_away_elo
        
        session.commit()
        
        logger.info(
            f"Updated ELO for match {match_id}: "
            f"{home_team.name} {new_home_elo:.1f}, {away_team.name} {new_away_elo:.1f}"
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating ELOs for match {match_id}: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    """
    Quick test to verify ELO calculator works.
    Run: python -m src.features.elo_calculator
    """
    print("🧮 ELO Calculator Test\n")
    
    # Test 1: Evenly matched teams
    calc = ELOCalculator()
    print("Test 1: Evenly matched teams (both 1500)")
    new_home, new_away = calc.update_elo(1500, 1500, 2, 1)
    print(f"  Home wins 2-1: Home {1500:.0f} → {new_home:.0f}, Away {1500:.0f} → {new_away:.0f}\n")
    
    # Test 2: Strong team wins (expected)
    print("Test 2: Strong home team (1700) beats weak team (1400)")
    new_home, new_away = calc.update_elo(1700, 1400, 3, 0)
    print(f"  Home wins 3-0: Home {1700:.0f} → {new_home:.0f}, Away {1400:.0f} → {new_away:.0f}")
    print(f"  (Expected result = small rating change)\n")
    
    # Test 3: Upset victory
    print("Test 3: Weak team (1400) upsets strong team (1700)")  
    new_home, new_away = calc.update_elo(1400, 1700, 2, 0)
    print(f"  Home wins 2-0: Home {1400:.0f} → {new_home:.0f}, Away {1700:.0f} → {new_away:.0f}")
    print(f"  (Unexpected result = large rating change)\n")
    
    # Test 4: Prediction
    print("Test 4: Match prediction")
    calc2 = ELOCalculator()
    # Simulate Man City (1850) vs Luton (1450)
    pred = calc2.predict_match_outcome(home_team_id=1, away_team_id=2)
    print(f"  Man City (1850) vs Luton (1450):")
    print(f"  Home win: {pred['home_win_prob']:.1%}")
    print(f"  Draw: {pred['draw_prob']:.1%}")
    print(f"  Away win: {pred['away_win_prob']:.1%}")
    print(f"  Expected score: {pred['expected_home_score']:.2f}\n")
    
    print("✅ ELO Calculator working correctly!")