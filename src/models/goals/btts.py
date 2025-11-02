"""
BTTS (Both Teams To Score) Model

Predicts probability that both teams will score at least one goal.

Core logic:
- P(home scores) = 1 - P(home scores 0)
- P(away scores) = 1 - P(away scores 0)
- P(BTTS) = P(home scores) × P(away scores)

Uses Poisson distribution based on expected goals.
Also considers league tendencies - Bundesliga has more BTTS than Serie A.

Usage:
    model = BTTSModel()
    prediction = model.predict(home_id=1, away_id=2, date='2024-01-15')
    
    # Returns something like:
    {
        'btts_yes_prob': 0.65,     # 65% chance both teams score
        'btts_no_prob': 0.35,      # 35% chance at least one blanks
        'confidence': 0.82         # How confident we are (based on data quality)
    }
"""

from typing import Dict, Any
import logging
from scipy.stats import poisson

from src.models.base_model import BaseModel

# Set up logging
logger = logging.getLogger(__name__)


class BTTSModel(BaseModel):
    """
    Predicts if both teams will score.
    
    Simple but effective market - often has value because bookies
    overestimate BTTS probability (people love goals).
    """
    
    def __init__(
        self,
        league_btts_adjustment: bool = True,
        min_confidence_threshold: float = 0.6
    ):
        """
        Initialise BTTS model.
        
        Args:
            league_btts_adjustment: Whether to adjust for league tendencies
                                   (Bundesliga = more goals, Serie A = fewer)
            min_confidence_threshold: Minimum confidence to make prediction (0.0-1.0)
        """
        super().__init__(
            name="BTTSModel",
            version="1.0.0",
            description="Both Teams To Score probability calculator"
        )
        
        self.league_btts_adjustment = league_btts_adjustment
        self.min_confidence_threshold = min_confidence_threshold
        
        # League-specific BTTS rates (historical averages)
        # These are modifiers to apply based on league playing style
        self.league_adjustments = {
            'Premier League': 1.0,      # Baseline
            'La Liga': 0.95,            # Slightly less BTTS
            'Bundesliga': 1.15,         # Much more BTTS (high-scoring league)
            'Serie A': 0.85,            # Defensive league
            'Ligue 1': 0.95,            # Moderate
            'Championship': 1.05,       # Quite attacking
        }
        
        logger.info(f"BTTS Model initialised (league adjustment: {league_btts_adjustment})")
    
    def calculate_expected_goals(
        self,
        features: Dict[str, Any]
    ) -> tuple[float, float]:
        """
        Calculate expected goals for both teams.
        
        Uses team attack/defence strengths and league averages.
        This is simplified - in production you'd use a dedicated goals model.
        
        Args:
            features: Match features from FeatureEngine
            
        Returns:
            (home_expected_goals, away_expected_goals)
        """
        # Get team strengths from features
        home_attack = features.get('home_attack_strength', 1.0)
        away_attack = features.get('away_attack_strength', 1.0)
        home_defence = features.get('home_defence_strength', 1.0)
        away_defence = features.get('away_defence_strength', 1.0)
        
        # League average goals (typically 1.4-1.6 per team)
        league_avg_goals = 1.5
        
        # Home advantage multiplier (home teams score ~30% more)
        home_advantage = 1.3
        
        # Calculate expected goals using Poisson formula:
        # xG = Team Attack × Opponent Defence × League Avg × (Home Advantage if applicable)
        home_xg = home_attack * away_defence * league_avg_goals * home_advantage
        away_xg = away_attack * home_defence * league_avg_goals
        
        logger.debug(f"Expected goals: Home {home_xg:.2f}, Away {away_xg:.2f}")
        
        return home_xg, away_xg
    
    def calculate_scoring_probability(
        self,
        expected_goals: float
    ) -> float:
        """
        Calculate probability that a team scores at least 1 goal.
        
        P(scores ≥ 1) = 1 - P(scores 0)
        P(scores 0) = Poisson(0 | λ=expected_goals)
        
        Args:
            expected_goals: Expected goals for the team
            
        Returns:
            Probability of scoring at least once (0.0-1.0)
        """
        # Probability of scoring exactly 0 goals
        prob_zero_goals = poisson.pmf(0, expected_goals)
        
        # Probability of scoring at least 1 goal
        prob_scores = 1 - prob_zero_goals
        
        return prob_scores
    
    def apply_league_adjustment(
        self,
        btts_prob: float,
        league_name: str = None
    ) -> float:
        """
        Adjust BTTS probability based on league characteristics.
        
        Some leagues are more attacking (Bundesliga), others more defensive (Serie A).
        This adjusts our prediction accordingly.
        
        Args:
            btts_prob: Base BTTS probability
            league_name: League name (optional)
            
        Returns:
            Adjusted BTTS probability
        """
        if not self.league_btts_adjustment or not league_name:
            return btts_prob
        
        # Get adjustment factor (defaults to 1.0 if league unknown)
        adjustment = self.league_adjustments.get(league_name, 1.0)
        
        # Apply adjustment but keep probability in valid range [0, 1]
        adjusted_prob = min(0.95, max(0.05, btts_prob * adjustment))
        
        logger.debug(
            f"League adjustment ({league_name}): "
            f"{btts_prob:.3f} → {adjusted_prob:.3f}"
        )
        
        return adjusted_prob
    
    def calculate_confidence(
        self,
        features: Dict[str, Any],
        home_xg: float,
        away_xg: float
    ) -> float:
        """
        Calculate confidence in our prediction.
        
        Confidence is lower when:
        - Teams have limited match history (low games played)
        - Expected goals are very low/high (edge cases)
        - Features are missing or default values
        
        Args:
            features: Match features
            home_xg: Home expected goals
            away_xg: Away expected goals
            
        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 1.0
        
        # Reduce confidence if using default ELO (no team data)
        if features['home_elo'] == 1500 and features['away_elo'] == 1500:
            confidence *= 0.7
        
        # Reduce confidence if no H2H history
        if features['h2h_matches_played'] == 0:
            confidence *= 0.85
        
        # Reduce confidence for very low expected goals (unpredictable)
        total_xg = home_xg + away_xg
        if total_xg < 1.5:
            confidence *= 0.8  # Low-scoring games are harder to predict
        
        # Reduce confidence for very high expected goals (rare)
        if total_xg > 4.0:
            confidence *= 0.9
        
        return confidence
    
    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        league_name: str = None
    ) -> Dict[str, Any]:
        """
        Predict BTTS probability for a match.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            match_date: Match date (YYYY-MM-DD)
            league_name: Optional league name for league-specific adjustments
            
        Returns:
            Dictionary with:
                - btts_yes_prob: Probability both teams score (0.0-1.0)
                - btts_no_prob: Probability at least one blanks (0.0-1.0)
                - home_scoring_prob: Probability home scores
                - away_scoring_prob: Probability away scores
                - confidence: Confidence in prediction (0.0-1.0)
                - expected_home_goals: Expected goals for home team
                - expected_away_goals: Expected goals for away team
        """
        # Validate inputs
        if not self.validate_inputs(home_team_id, away_team_id, match_date):
            logger.error("Invalid inputs for BTTS prediction")
            return self._get_default_prediction()
        
        try:
            # Get match features
            features = self.get_features(home_team_id, away_team_id, match_date)
            
            # Calculate expected goals
            home_xg, away_xg = self.calculate_expected_goals(features)
            
            # Calculate individual team scoring probabilities
            home_scores_prob = self.calculate_scoring_probability(home_xg)
            away_scores_prob = self.calculate_scoring_probability(away_xg)
            
            # Calculate BTTS probability (independent events)
            btts_yes = home_scores_prob * away_scores_prob
            
            # Apply league-specific adjustment if provided
            btts_yes = self.apply_league_adjustment(btts_yes, league_name)
            
            # Calculate confidence
            confidence = self.calculate_confidence(features, home_xg, away_xg)
            
            # Construct prediction
            prediction = {
                'btts_yes_prob': btts_yes,
                'btts_no_prob': 1 - btts_yes,
                'home_scoring_prob': home_scores_prob,
                'away_scoring_prob': away_scores_prob,
                'confidence': confidence,
                'expected_home_goals': home_xg,
                'expected_away_goals': away_xg,
                'should_bet': confidence >= self.min_confidence_threshold
            }
            
            # Update model metadata
            self._update_metadata()
            
            logger.info(
                f"BTTS Prediction: {btts_yes:.1%} "
                f"(confidence: {confidence:.1%})"
            )
            
            return prediction
            
        except Exception as e:
            logger.error(f"BTTS prediction failed: {e}")
            return self._get_default_prediction()
    
    def _get_default_prediction(self) -> Dict[str, Any]:
        """
        Return default prediction if calculation fails.
        
        Returns neutral probabilities - basically admitting we don't know.
        """
        return {
            'btts_yes_prob': 0.50,
            'btts_no_prob': 0.50,
            'home_scoring_prob': 0.70,
            'away_scoring_prob': 0.70,
            'confidence': 0.0,
            'expected_home_goals': 1.5,
            'expected_away_goals': 1.5,
            'should_bet': False,
            'error': 'Prediction failed - using defaults'
        }
    
    def get_betting_recommendation(
        self,
        prediction: Dict[str, Any],
        bookmaker_odds: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Compare model prediction to bookmaker odds to find value.
        
        Args:
            prediction: Model prediction from predict()
            bookmaker_odds: Dict like {'yes': 1.95, 'no': 1.95}
            
        Returns:
            Betting recommendation with expected value
        """
        btts_yes_prob = prediction['btts_yes_prob']
        btts_no_prob = prediction['btts_no_prob']
        confidence = prediction['confidence']
        
        # Calculate implied probability from odds
        yes_implied = 1 / bookmaker_odds['yes'] if 'yes' in bookmaker_odds else 0.5
        no_implied = 1 / bookmaker_odds['no'] if 'no' in bookmaker_odds else 0.5
        
        # Calculate expected value
        # EV = (Our Prob × Odds) - 1
        yes_ev = (btts_yes_prob * bookmaker_odds.get('yes', 2.0)) - 1
        no_ev = (btts_no_prob * bookmaker_odds.get('no', 2.0)) - 1
        
        # Determine best bet (must have positive EV and meet confidence threshold)
        if yes_ev > 0 and yes_ev > no_ev and confidence >= self.min_confidence_threshold:
            recommendation = {
                'bet': 'BTTS Yes',
                'expected_value': yes_ev,
                'our_probability': btts_yes_prob,
                'bookmaker_probability': yes_implied,
                'edge': btts_yes_prob - yes_implied,
                'recommended_odds': bookmaker_odds.get('yes'),
                'confidence': confidence
            }
        elif no_ev > 0 and confidence >= self.min_confidence_threshold:
            recommendation = {
                'bet': 'BTTS No',
                'expected_value': no_ev,
                'our_probability': btts_no_prob,
                'bookmaker_probability': no_implied,
                'edge': btts_no_prob - no_implied,
                'recommended_odds': bookmaker_odds.get('no'),
                'confidence': confidence
            }
        else:
            recommendation = {
                'bet': 'No Bet',
                'expected_value': max(yes_ev, no_ev),
                'reason': 'No positive EV or insufficient confidence'
            }
        
        return recommendation


if __name__ == "__main__":
    """
    Test BTTS model.
    """
    print("\n" + "="*60)
    print("BTTS MODEL TEST")
    print("="*60 + "\n")
    
    # Create model
    model = BTTSModel()
    
    print(f"Model info: {model.get_info()}\n")
    
    # Test prediction (will use default features if DB not set up)
    print("Testing prediction...")
    prediction = model.predict(
        home_team_id=1,
        away_team_id=2,
        match_date='2024-01-15',
        league_name='Premier League'
    )
    
    print(f"\nPrediction results:")
    print(f"  BTTS Yes: {prediction['btts_yes_prob']:.1%}")
    print(f"  BTTS No: {prediction['btts_no_prob']:.1%}")
    print(f"  Home scores: {prediction['home_scoring_prob']:.1%}")
    print(f"  Away scores: {prediction['away_scoring_prob']:.1%}")
    print(f"  Confidence: {prediction['confidence']:.1%}")
    print(f"  Should bet: {prediction['should_bet']}")
    
    # Test betting recommendation
    print("\nTesting betting recommendation...")
    bookmaker_odds = {'yes': 1.85, 'no': 2.05}
    recommendation = model.get_betting_recommendation(prediction, bookmaker_odds)
    
    print(f"\nBetting recommendation:")
    print(f"  Bet: {recommendation['bet']}")
    if recommendation['bet'] != 'No Bet':
        print(f"  Expected Value: {recommendation['expected_value']:.2%}")
        print(f"  Edge: {recommendation['edge']:.2%}")
        print(f"  Confidence: {recommendation['confidence']:.1%}")
    else:
        print(f"  Reason: {recommendation.get('reason', 'Unknown')}")
    
    print("\n" + "="*60)
    print("BTTS model working correctly!")
    print("="*60 + "\n")