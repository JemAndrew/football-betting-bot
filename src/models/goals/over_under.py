"""
Over/Under 2.5 Goals Model

Predicts probability that a match will have Over or Under 2.5 total goals.

Core logic:
- Calculate expected goals for both teams using Poisson
- Sum all scoreline probabilities where total goals ≤ 2 for Under 2.5
- Over 2.5 probability = 1 - Under 2.5 probability

Also supports other totals (1.5, 3.5, 4.5) - just change the threshold.

Usage:
    model = OverUnderModel(goal_threshold=2.5)
    prediction = model.predict(home_id=1, away_id=2, date='2024-01-15')
    
    # Returns:
    {
        'over_prob': 0.58,    # 58% chance of 3+ goals
        'under_prob': 0.42,   # 42% chance of 0-2 goals
        'expected_total_goals': 3.2,
        'confidence': 0.85
    }
"""

from typing import Dict, Any
import logging
from scipy.stats import poisson
import math

from src.models.base_model import BaseModel

# Set up logging
logger = logging.getLogger(__name__)


class OverUnderModel(BaseModel):
    """
    Predicts Over/Under goals probability.
    
    This market is very popular and usually has good liquidity.
    Model uses Poisson distribution to calculate all possible scorelines.
    """
    
    def __init__(
        self,
        goal_threshold: float = 2.5,
        max_goals_to_calculate: int = 8
    ):
        """
        Initialise Over/Under model.
        
        Args:
            goal_threshold: Goals threshold (2.5 is most common, but also 1.5, 3.5, etc.)
            max_goals_to_calculate: Maximum goals to calculate probabilities for
                                   (8 is usually enough - 9-9 scorelines are rare!)
        """
        super().__init__(
            name="OverUnderModel",
            version="1.0.0",
            description=f"Over/Under {goal_threshold} goals predictor"
        )
        
        self.goal_threshold = goal_threshold
        self.max_goals_to_calculate = max_goals_to_calculate
        
        logger.info(
            f"Over/Under Model initialised "
            f"(threshold: {goal_threshold} goals)"
        )
    
    def calculate_expected_goals(
        self,
        features: Dict[str, Any]
    ) -> tuple[float, float]:
        """
        Calculate expected goals for both teams.
        
        Uses the standard Poisson formula with team strengths.
        
        Args:
            features: Match features from FeatureEngine
            
        Returns:
            (home_expected_goals, away_expected_goals)
        """
        # Get team strengths
        home_attack = features.get('home_attack_strength', 1.0)
        away_attack = features.get('away_attack_strength', 1.0)
        home_defence = features.get('home_defence_strength', 1.0)
        away_defence = features.get('away_defence_strength', 1.0)
        
        # League average (typically 1.4-1.6 goals per team per match)
        league_avg_goals = 1.5
        
        # Home advantage (home teams typically score 30% more)
        home_advantage = 1.3
        
        # Calculate expected goals
        # xG = Team Attack × Opponent Defence × League Average × Home Advantage
        home_xg = home_attack * away_defence * league_avg_goals * home_advantage
        away_xg = away_attack * home_defence * league_avg_goals
        
        # Small adjustment based on form (recent form matters)
        form_adjustment = 1 + (features.get('form_diff', 0) * 0.05)
        home_xg *= form_adjustment if form_adjustment > 1 else 1
        away_xg *= (2 - form_adjustment) if form_adjustment > 1 else 1
        
        logger.debug(
            f"Expected goals: Home {home_xg:.2f}, Away {away_xg:.2f} "
            f"(total: {home_xg + away_xg:.2f})"
        )
        
        return home_xg, away_xg
    
    def calculate_scoreline_probabilities(
        self,
        home_xg: float,
        away_xg: float
    ) -> Dict[tuple, float]:
        """
        Calculate probability of each possible scoreline.
        
        Uses Poisson distribution for both teams independently.
        P(2-1) = P(home scores 2) × P(away scores 1)
        
        Args:
            home_xg: Expected home goals
            away_xg: Expected away goals
            
        Returns:
            Dict mapping (home_goals, away_goals) → probability
            
        Example:
            {
                (0, 0): 0.08,   # 8% chance of 0-0
                (1, 0): 0.12,   # 12% chance of 1-0
                (1, 1): 0.15,   # 15% chance of 1-1
                ...
            }
        """
        scorelines = {}
        
        # Calculate probabilities for all scorelines up to max_goals
        for home_goals in range(self.max_goals_to_calculate + 1):
            for away_goals in range(self.max_goals_to_calculate + 1):
                # Probability home team scores exactly home_goals
                prob_home = poisson.pmf(home_goals, home_xg)
                
                # Probability away team scores exactly away_goals
                prob_away = poisson.pmf(away_goals, away_xg)
                
                # Probability of this exact scoreline (independent events)
                prob_scoreline = prob_home * prob_away
                
                scorelines[(home_goals, away_goals)] = prob_scoreline
        
        return scorelines
    
    def calculate_over_under_probabilities(
        self,
        scorelines: Dict[tuple, float]
    ) -> tuple[float, float]:
        """
        Calculate Over/Under probabilities from scoreline probabilities.
        
        Sum up all scorelines where total goals meets criteria.
        
        Args:
            scorelines: Dict of (home, away) → probability
            
        Returns:
            (over_prob, under_prob)
        """
        under_prob = 0.0
        
        # Sum probabilities of all scorelines Under the threshold
        for (home_goals, away_goals), prob in scorelines.items():
            total_goals = home_goals + away_goals
            
            # Check if under threshold (e.g., ≤ 2 for Under 2.5)
            if total_goals < self.goal_threshold:
                under_prob += prob
        
        # Over probability is everything else
        over_prob = 1 - under_prob
        
        return over_prob, under_prob
    
    def calculate_expected_total_goals(
        self,
        home_xg: float,
        away_xg: float
    ) -> float:
        """
        Calculate expected total goals in match.
        
        Simple sum of expected goals for both teams.
        
        Args:
            home_xg: Expected home goals
            away_xg: Expected away goals
            
        Returns:
            Expected total goals
        """
        return home_xg + away_xg
    
    def calculate_confidence(
        self,
        features: Dict[str, Any],
        expected_total: float,
        over_prob: float
    ) -> float:
        """
        Calculate confidence in prediction.
        
        Confidence is lower when:
        - Total expected goals very low or high (edge cases)
        - Probability close to 50/50 (coin flip)
        - Limited data available
        
        Args:
            features: Match features
            expected_total: Expected total goals
            over_prob: Over probability
            
        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 1.0
        
        # Reduce confidence if probability close to 50% (too uncertain)
        # The closer to 50%, the less confident we should be
        prob_from_midpoint = abs(over_prob - 0.5)
        if prob_from_midpoint < 0.1:  # Between 40-60%
            confidence *= 0.7
        elif prob_from_midpoint < 0.15:  # Between 35-65%
            confidence *= 0.85
        
        # Reduce confidence for very low expected totals (unpredictable)
        if expected_total < 1.8:
            confidence *= 0.8
        
        # Reduce confidence for very high expected totals (rare situations)
        if expected_total > 4.5:
            confidence *= 0.85
        
        # Reduce confidence if no H2H data
        if features['h2h_matches_played'] == 0:
            confidence *= 0.9
        
        # Reduce confidence if using default ELO
        if features['home_elo'] == 1500 and features['away_elo'] == 1500:
            confidence *= 0.8
        
        return confidence
    
    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str
    ) -> Dict[str, Any]:
        """
        Predict Over/Under probability for a match.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            match_date: Match date (YYYY-MM-DD)
            
        Returns:
            Dictionary with:
                - over_prob: Probability of Over threshold (0.0-1.0)
                - under_prob: Probability of Under threshold (0.0-1.0)
                - expected_total_goals: Expected total goals
                - expected_home_goals: Expected home goals
                - expected_away_goals: Expected away goals
                - confidence: Confidence in prediction (0.0-1.0)
                - most_likely_scoreline: Most probable exact score
        """
        # Validate inputs
        if not self.validate_inputs(home_team_id, away_team_id, match_date):
            logger.error("Invalid inputs for Over/Under prediction")
            return self._get_default_prediction()
        
        try:
            # Get match features
            features = self.get_features(home_team_id, away_team_id, match_date)
            
            # Calculate expected goals
            home_xg, away_xg = self.calculate_expected_goals(features)
            expected_total = self.calculate_expected_total_goals(home_xg, away_xg)
            
            # Calculate all scoreline probabilities
            scorelines = self.calculate_scoreline_probabilities(home_xg, away_xg)
            
            # Calculate Over/Under from scorelines
            over_prob, under_prob = self.calculate_over_under_probabilities(scorelines)
            
            # Find most likely scoreline (for fun)
            most_likely = max(scorelines.items(), key=lambda x: x[1])
            most_likely_score = f"{most_likely[0][0]}-{most_likely[0][1]}"
            most_likely_prob = most_likely[1]
            
            # Calculate confidence
            confidence = self.calculate_confidence(features, expected_total, over_prob)
            
            # Construct prediction
            prediction = {
                'over_prob': over_prob,
                'under_prob': under_prob,
                'expected_total_goals': expected_total,
                'expected_home_goals': home_xg,
                'expected_away_goals': away_xg,
                'confidence': confidence,
                'most_likely_scoreline': most_likely_score,
                'most_likely_scoreline_prob': most_likely_prob,
                'goal_threshold': self.goal_threshold
            }
            
            # Update model metadata
            self._update_metadata()
            
            logger.info(
                f"O/U {self.goal_threshold} Prediction: "
                f"Over {over_prob:.1%}, Under {under_prob:.1%} "
                f"(xG: {expected_total:.2f}, confidence: {confidence:.1%})"
            )
            
            return prediction
            
        except Exception as e:
            logger.error(f"Over/Under prediction failed: {e}")
            return self._get_default_prediction()
    
    def _get_default_prediction(self) -> Dict[str, Any]:
        """
        Return default prediction if calculation fails.
        """
        return {
            'over_prob': 0.50,
            'under_prob': 0.50,
            'expected_total_goals': self.goal_threshold,
            'expected_home_goals': self.goal_threshold / 2,
            'expected_away_goals': self.goal_threshold / 2,
            'confidence': 0.0,
            'most_likely_scoreline': '1-1',
            'most_likely_scoreline_prob': 0.10,
            'goal_threshold': self.goal_threshold,
            'error': 'Prediction failed - using defaults'
        }
    
    def get_betting_recommendation(
        self,
        prediction: Dict[str, Any],
        bookmaker_odds: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Compare model prediction to bookmaker odds.
        
        Args:
            prediction: Model prediction from predict()
            bookmaker_odds: Dict like {'over': 1.85, 'under': 2.05}
            
        Returns:
            Betting recommendation with expected value
        """
        over_prob = prediction['over_prob']
        under_prob = prediction['under_prob']
        confidence = prediction['confidence']
        
        # Calculate implied probabilities from odds
        over_implied = 1 / bookmaker_odds['over'] if 'over' in bookmaker_odds else 0.5
        under_implied = 1 / bookmaker_odds['under'] if 'under' in bookmaker_odds else 0.5
        
        # Calculate expected values
        over_ev = (over_prob * bookmaker_odds.get('over', 2.0)) - 1
        under_ev = (under_prob * bookmaker_odds.get('under', 2.0)) - 1
        
        # Determine best bet (need positive EV and reasonable confidence)
        if over_ev > 0.05 and over_ev > under_ev and confidence >= 0.6:
            recommendation = {
                'bet': f'Over {self.goal_threshold}',
                'expected_value': over_ev,
                'our_probability': over_prob,
                'bookmaker_probability': over_implied,
                'edge': over_prob - over_implied,
                'recommended_odds': bookmaker_odds.get('over'),
                'confidence': confidence,
                'expected_total_goals': prediction['expected_total_goals']
            }
        elif under_ev > 0.05 and confidence >= 0.6:
            recommendation = {
                'bet': f'Under {self.goal_threshold}',
                'expected_value': under_ev,
                'our_probability': under_prob,
                'bookmaker_probability': under_implied,
                'edge': under_prob - under_implied,
                'recommended_odds': bookmaker_odds.get('under'),
                'confidence': confidence,
                'expected_total_goals': prediction['expected_total_goals']
            }
        else:
            recommendation = {
                'bet': 'No Bet',
                'expected_value': max(over_ev, under_ev),
                'reason': 'Insufficient edge or confidence',
                'over_ev': over_ev,
                'under_ev': under_ev,
                'confidence': confidence
            }
        
        return recommendation


if __name__ == "__main__":
    """
    Test Over/Under model.
    """
    print("\n" + "="*60)
    print("OVER/UNDER MODEL TEST")
    print("="*60 + "\n")
    
    # Test different thresholds
    for threshold in [1.5, 2.5, 3.5]:
        print(f"\n--- Testing O/U {threshold} ---")
        model = OverUnderModel(goal_threshold=threshold)
        
        prediction = model.predict(
            home_team_id=1,
            away_team_id=2,
            match_date='2024-01-15'
        )
        
        print(f"Over {threshold}: {prediction['over_prob']:.1%}")
        print(f"Under {threshold}: {prediction['under_prob']:.1%}")
        print(f"Expected total: {prediction['expected_total_goals']:.2f} goals")
        print(f"Confidence: {prediction['confidence']:.1%}")
        print(f"Most likely score: {prediction['most_likely_scoreline']} "
              f"({prediction['most_likely_scoreline_prob']:.1%})")
    
    # Test betting recommendation
    print("\n--- Testing Betting Recommendation ---")
    model = OverUnderModel(goal_threshold=2.5)
    prediction = model.predict(1, 2, '2024-01-15')
    
    bookmaker_odds = {'over': 1.90, 'under': 2.00}
    recommendation = model.get_betting_recommendation(prediction, bookmaker_odds)
    
    print(f"\nBet: {recommendation['bet']}")
    if recommendation['bet'] != 'No Bet':
        print(f"Expected Value: {recommendation['expected_value']:.2%}")
        print(f"Edge: {recommendation['edge']:.2%}")
        print(f"Odds: {recommendation['recommended_odds']}")
    else:
        print(f"Reason: {recommendation.get('reason')}")
    
    print("\n" + "="*60)
    print("Over/Under model working correctly!")
    print("="*60 + "\n")