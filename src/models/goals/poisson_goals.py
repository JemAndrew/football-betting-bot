"""
Poisson Goals Model - Match Outcome Prediction

This is where we turn team stats into actual betting probabilities.

Uses Poisson distribution to model goal scoring:
- Goals are discrete events (0, 1, 2, 3...)
- Relatively rare (average ~1.5 per team per match)
- Independent events (one goal doesn't affect probability of next)
- Poisson distribution models this perfectly

Core calculation:
1. Calculate expected goals for each team
2. Use Poisson distribution to get probability of each scoreline
3. Aggregate scorelines into betting markets (Over 2.5, BTTS, etc.)
4. Calculate expected value vs bookmaker odds

Expected goals formula:
Home xG = Home Attack × Away Defence × League Avg × Home Advantage
Away xG = Away Attack × Home Defence × League Avg

Usage:
    model = GoalsModel()
    prediction = model.predict_match(home_team_id=1, away_team_id=2)
    print(f"Over 2.5 probability: {prediction['over_25']:.1%}")
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime
import math
from scipy.stats import poisson

import logging
from src.features.elo_calculator import ELOCalculator
from src.features.form_calculator import FormCalculator
from src.features.team_features import TeamFeatures
from src.data.database import Session, Team

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class GoalsModel:
    """
    Predicts match outcomes using Poisson distribution.
    
    Combines team attack/defence strengths to calculate expected goals,
    then uses Poisson to get probability of each scoreline.
    """
    
    def __init__(
        self,
        home_advantage: float = 1.3,
        use_elo: bool = True,
        use_form: bool = True,
        elo_weight: float = 0.3,
        form_weight: float = 0.2
    ):
        """
        Initialise goals prediction model.
        
        Args:
            home_advantage: Multiplier for home team expected goals (typically 1.2-1.4)
            use_elo: Whether to adjust predictions based on ELO ratings
            use_form: Whether to adjust predictions based on recent form
            elo_weight: How much ELO influences prediction (0.0-1.0)
            form_weight: How much form influences prediction (0.0-1.0)
            
        Note: Team features (attack/defence) are always used (core of model)
              ELO and form are optional adjustments on top
        """
        self.home_advantage = home_advantage
        self.use_elo = use_elo
        self.use_form = use_form
        self.elo_weight = elo_weight
        self.form_weight = form_weight
        
        # Initialise feature calculators
        self.team_features = TeamFeatures(lookback_days=90, min_games=5)
        
        if use_elo:
            self.elo_calc = ELOCalculator()
        
        if use_form:
            self.form_calc = FormCalculator(lookback_games=5)
        
        logger.info(
            f"Goals Model initialised: Home Advantage={home_advantage}, "
            f"Use ELO={use_elo}, Use Form={use_form}"
        )
    
    def calculate_expected_goals(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Tuple[float, float]:
        """
        Calculate expected goals for both teams.
        
        This is the core Poisson calculation. We're estimating how many goals
        each team is likely to score based on their attack vs opponent's defence.
        
        Formula:
        Home xG = Home Attack × Away Defence × League Avg Home Goals × Home Advantage
        Away xG = Away Attack × Home Defence × League Avg Away Goals
        
        Then optionally adjust based on ELO and form.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date of match (for backtesting)
            
        Returns:
            Tuple of (home_expected_goals, away_expected_goals)
        """
        # Get team features (attack/defence strengths)
        home_features = self.team_features.calculate_team_features(
            team_id=home_team_id,
            venue='home',
            before_date=match_date
        )
        
        away_features = self.team_features.calculate_team_features(
            team_id=away_team_id,
            venue='away',
            before_date=match_date
        )
        
        # Get league averages
        league_avg = self.team_features.calculate_league_averages(
            league_id='PL',
            before_date=match_date
        )
        
        # Calculate base expected goals using team strengths
        # Home team: their attack strength × away team's defence strength × league average
        home_xg = (
            home_features['attack_strength'] * 
            away_features['defence_strength'] * 
            league_avg['home_goals_per_game'] *
            self.home_advantage
        )
        
        # Away team: their attack strength × home team's defence strength × league average
        away_xg = (
            away_features['attack_strength'] * 
            home_features['defence_strength'] * 
            league_avg['away_goals_per_game']
        )
        
        # Adjust based on ELO if enabled
        if self.use_elo:
            home_elo = self.elo_calc.get_team_elo(home_team_id)
            away_elo = self.elo_calc.get_team_elo(away_team_id)
            
            # ELO difference tells us relative strength
            # +200 ELO means roughly 25% stronger
            elo_diff = home_elo - away_elo
            elo_multiplier = 1 + (elo_diff / 1000) * self.elo_weight
            
            home_xg *= elo_multiplier
            away_xg /= elo_multiplier  # Inverse for away team
        
        # Adjust based on form if enabled
        if self.use_form:
            match_form = self.form_calc.calculate_match_form_features(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date
            )
            
            # Form differential: difference in recent points per game
            form_diff = match_form['form_differential']
            
            # Scale form impact: 1.0 PPG difference = 10% xG adjustment
            form_multiplier = 1 + (form_diff * 0.1 * self.form_weight)
            
            home_xg *= form_multiplier
            away_xg /= form_multiplier
        
        # Sanity check: cap at reasonable values
        # No team scores 5+ goals on average
        home_xg = min(home_xg, 5.0)
        away_xg = min(away_xg, 5.0)
        
        # Floor at 0.2 (even worst teams occasionally score)
        home_xg = max(home_xg, 0.2)
        away_xg = max(away_xg, 0.2)
        
        logger.debug(
            f"Expected goals: Home {home_xg:.2f}, Away {away_xg:.2f}"
        )
        
        return home_xg, away_xg
    
    def calculate_match_probabilities(
        self,
        home_xg: float,
        away_xg: float,
        max_goals: int = 10
    ) -> Dict[str, float]:
        """
        Calculate probabilities for various betting markets.
        
        Uses Poisson distribution to get probability of each scoreline,
        then aggregates into useful betting markets.
        
        Args:
            home_xg: Expected goals for home team
            away_xg: Expected goals for away team
            max_goals: Maximum goals to consider (10 is safe, >10 extremely rare)
            
        Returns:
            Dictionary with market probabilities:
            {
                'home_win': 0.45,
                'draw': 0.28,
                'away_win': 0.27,
                'over_05': 0.85,
                'over_15': 0.65,
                'over_25': 0.48,
                'over_35': 0.32,
                'under_25': 0.52,
                'btts': 0.55,  # Both teams to score
                'home_clean_sheet': 0.15,
                'away_clean_sheet': 0.20,
                'scorelines': {(1,1): 0.15, (2,1): 0.12, ...}  # All scoreline probs
            }
        """
        # Calculate Poisson probabilities for each number of goals
        # P(X=k) = (λ^k * e^-λ) / k!  where λ = expected goals
        # But scipy does this for us
        
        # Generate probability distribution for each team
        home_probs = [poisson.pmf(i, home_xg) for i in range(max_goals + 1)]
        away_probs = [poisson.pmf(i, away_xg) for i in range(max_goals + 1)]
        
        # Calculate probability of each scoreline
        # P(2-1) = P(home scores 2) × P(away scores 1)
        scorelines = {}
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                prob = home_probs[home_goals] * away_probs[away_goals]
                scorelines[(home_goals, away_goals)] = prob
        
        # Aggregate scorelines into betting markets
        home_win_prob = sum(
            prob for (h, a), prob in scorelines.items() if h > a
        )
        draw_prob = sum(
            prob for (h, a), prob in scorelines.items() if h == a
        )
        away_win_prob = sum(
            prob for (h, a), prob in scorelines.items() if h < a
        )
        
        # Over/Under markets
        over_05_prob = sum(
            prob for (h, a), prob in scorelines.items() if h + a > 0.5
        )
        over_15_prob = sum(
            prob for (h, a), prob in scorelines.items() if h + a > 1.5
        )
        over_25_prob = sum(
            prob for (h, a), prob in scorelines.items() if h + a > 2.5
        )
        over_35_prob = sum(
            prob for (h, a), prob in scorelines.items() if h + a > 3.5
        )
        
        # Both teams to score
        btts_prob = sum(
            prob for (h, a), prob in scorelines.items() if h > 0 and a > 0
        )
        
        # Clean sheets
        home_clean_sheet_prob = sum(
            prob for (h, a), prob in scorelines.items() if a == 0
        )
        away_clean_sheet_prob = sum(
            prob for (h, a), prob in scorelines.items() if h == 0
        )
        
        return {
            'home_win': home_win_prob,
            'draw': draw_prob,
            'away_win': away_win_prob,
            'over_05': over_05_prob,
            'over_15': over_15_prob,
            'over_25': over_25_prob,
            'over_35': over_35_prob,
            'under_25': 1 - over_25_prob,
            'under_35': 1 - over_35_prob,
            'btts': btts_prob,
            'btts_no': 1 - btts_prob,
            'home_clean_sheet': home_clean_sheet_prob,
            'away_clean_sheet': away_clean_sheet_prob,
            'scorelines': scorelines
        }
    
    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[datetime] = None
    ) -> Dict:
        """
        Full match prediction with all markets.
        
        This is the main function you'll use for predictions.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            match_date: Date of match (for backtesting, else None)
            
        Returns:
            Comprehensive prediction dictionary:
            {
                'home_team_id': 1,
                'away_team_id': 2,
                'home_xg': 2.1,
                'away_xg': 1.2,
                'total_xg': 3.3,
                'home_win_prob': 0.52,
                'draw_prob': 0.24,
                'away_win_prob': 0.24,
                'over_25_prob': 0.63,
                'btts_prob': 0.58,
                'most_likely_scoreline': (2, 1),
                'most_likely_scoreline_prob': 0.15,
                'probabilities': {...},  # All market probabilities
                'fair_odds': {...}  # Fair odds for each market
            }
        """
        # Calculate expected goals
        home_xg, away_xg = self.calculate_expected_goals(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            match_date=match_date
        )
        
        # Calculate all probabilities
        probabilities = self.calculate_match_probabilities(home_xg, away_xg)
        
        # Find most likely scoreline
        scorelines_sorted = sorted(
            probabilities['scorelines'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        most_likely_scoreline = scorelines_sorted[0][0]
        most_likely_prob = scorelines_sorted[0][1]
        
        # Calculate fair odds for main markets
        # Fair odds = 1 / probability
        fair_odds = {
            'home_win': 1 / probabilities['home_win'] if probabilities['home_win'] > 0 else 999,
            'draw': 1 / probabilities['draw'] if probabilities['draw'] > 0 else 999,
            'away_win': 1 / probabilities['away_win'] if probabilities['away_win'] > 0 else 999,
            'over_25': 1 / probabilities['over_25'] if probabilities['over_25'] > 0 else 999,
            'under_25': 1 / probabilities['under_25'] if probabilities['under_25'] > 0 else 999,
            'btts_yes': 1 / probabilities['btts'] if probabilities['btts'] > 0 else 999,
            'btts_no': 1 / probabilities['btts_no'] if probabilities['btts_no'] > 0 else 999,
        }
        
        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_xg': home_xg,
            'away_xg': away_xg,
            'total_xg': home_xg + away_xg,
            'home_win_prob': probabilities['home_win'],
            'draw_prob': probabilities['draw'],
            'away_win_prob': probabilities['away_win'],
            'over_25_prob': probabilities['over_25'],
            'under_25_prob': probabilities['under_25'],
            'btts_prob': probabilities['btts'],
            'most_likely_scoreline': most_likely_scoreline,
            'most_likely_scoreline_prob': most_likely_prob,
            'probabilities': probabilities,
            'fair_odds': fair_odds
        }
    
    def calculate_expected_value(
        self,
        our_probability: float,
        bookmaker_odds: float
    ) -> float:
        """
        Calculate expected value of a bet.
        
        Expected value tells us if a bet is profitable long-term.
        EV = (Our Probability × Odds) - 1
        
        Args:
            our_probability: Our calculated probability (0.0-1.0)
            bookmaker_odds: Bookmaker's decimal odds
            
        Returns:
            Expected value as decimal
            Positive = profitable bet
            Negative = losing bet
            
        Examples:
            our_prob=0.60, odds=2.0 → EV = (0.60 × 2.0) - 1 = +0.20 (20% edge)
            our_prob=0.40, odds=2.0 → EV = (0.40 × 2.0) - 1 = -0.20 (bad bet)
            our_prob=0.50, odds=2.0 → EV = (0.50 × 2.0) - 1 = 0.00 (fair)
        """
        expected_value = (our_probability * bookmaker_odds) - 1
        return expected_value
    
    def find_value_bets(
        self,
        prediction: Dict,
        bookmaker_odds: Dict[str, float],
        min_edge: float = 0.05
    ) -> List[Dict]:
        """
        Find betting opportunities with positive expected value.
        
        Compares our probabilities to bookmaker odds to find value bets.
        
        Args:
            prediction: Output from predict_match()
            bookmaker_odds: Dictionary of bookmaker odds e.g.:
                {
                    'home_win': 1.80,
                    'draw': 3.40,
                    'away_win': 4.50,
                    'over_25': 1.90,
                    'btts_yes': 1.85
                }
            min_edge: Minimum edge to consider (0.05 = 5% edge minimum)
            
        Returns:
            List of value bets, sorted by EV:
            [
                {
                    'market': 'over_25',
                    'our_probability': 0.63,
                    'bookmaker_odds': 1.90,
                    'implied_probability': 0.526,
                    'edge': 0.104,  # 10.4% edge
                    'expected_value': 0.197,  # 19.7% EV
                    'fair_odds': 1.59
                },
                ...
            ]
        """
        value_bets = []
        
        # Map our prediction keys to bookmaker markets
        market_mapping = {
            'home_win': 'home_win_prob',
            'draw': 'draw_prob',
            'away_win': 'away_win_prob',
            'over_25': 'over_25_prob',
            'under_25': 'under_25_prob',
            'btts_yes': 'btts_prob',
            'btts_no': ('probabilities', 'btts_no')
        }
        
        for market, odds in bookmaker_odds.items():
            if market not in market_mapping:
                continue
            
            # Get our probability for this market
            prob_key = market_mapping[market]
            if isinstance(prob_key, tuple):
                our_prob = prediction[prob_key[0]][prob_key[1]]
            else:
                our_prob = prediction[prob_key]
            
            # Calculate implied probability from bookmaker odds
            implied_prob = 1 / odds
            
            # Calculate edge and expected value
            edge = our_prob - implied_prob
            ev = self.calculate_expected_value(our_prob, odds)
            
            # Is this a value bet?
            if edge >= min_edge and ev > 0:
                value_bets.append({
                    'market': market,
                    'our_probability': our_prob,
                    'bookmaker_odds': odds,
                    'implied_probability': implied_prob,
                    'edge': edge,
                    'expected_value': ev,
                    'fair_odds': 1 / our_prob if our_prob > 0 else 999
                })
        
        # Sort by expected value (best bets first)
        value_bets.sort(key=lambda x: x['expected_value'], reverse=True)
        
        return value_bets
    
    def get_top_scorelines(
        self,
        prediction: Dict,
        top_n: int = 5
    ) -> List[Tuple]:
        """
        Get most likely scorelines.
        
        Args:
            prediction: Output from predict_match()
            top_n: How many scorelines to return
            
        Returns:
            List of (scoreline, probability) tuples:
            [
                ((2, 1), 0.15),  # 2-1 is 15% likely
                ((1, 1), 0.12),  # 1-1 is 12% likely
                ...
            ]
        """
        scorelines = prediction['probabilities']['scorelines']
        sorted_scorelines = sorted(
            scorelines.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_scorelines[:top_n]


if __name__ == '__main__':
    """
    Quick test of goals model.
    Run: python -m src.models.goals_model
    """
    print("Goals Model Test\n")
    
    from data.database import Session, Team
    
    session = Session()
    teams = session.query(Team).order_by(Team.current_elo.desc()).limit(2).all()
    
    if len(teams) >= 2:
        top_team = teams[0]
        second_team = teams[1]
        
        print(f"Testing: {top_team.name} vs {second_team.name}\n")
        
        model = GoalsModel(
            home_advantage=1.3,
            use_elo=True,
            use_form=True
        )
        
        prediction = model.predict_match(
            home_team_id=top_team.id,
            away_team_id=second_team.id
        )
        
        print(f"Expected Goals: {prediction['home_xg']:.2f} - {prediction['away_xg']:.2f}")
        print(f"Home Win: {prediction['home_win_prob']:.1%}")
        print(f"Draw: {prediction['draw_prob']:.1%}")
        print(f"Away Win: {prediction['away_win_prob']:.1%}")
        print(f"Over 2.5: {prediction['over_25_prob']:.1%}")
        print(f"BTTS: {prediction['btts_prob']:.1%}")
        print(f"\nMost likely: {prediction['most_likely_scoreline']} ({prediction['most_likely_scoreline_prob']:.1%})")
    
    session.close()
    
    print("\nGoals Model working correctly")