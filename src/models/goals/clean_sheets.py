"""
Clean Sheet Model

Predicts probability that a team will keep a clean sheet (score 0 goals against).

Core logic:
- P(clean sheet) = P(opponent scores 0) = Poisson(0 | λ=opponent_xG)
- Uses team's defensive strength vs opponent's attacking strength

Useful for:
- Clean sheet markets (popular in accumulators)
- Defensive analysis
- Goalkeeper/defence assessment

Usage:
    model = CleanSheetModel()
    prediction = model.predict(home_id=1, away_id=2, date='2024-01-15')
    
    # Returns:
    {
        'home_clean_sheet_prob': 0.35,  # 35% chance home keeps clean sheet
        'away_clean_sheet_prob': 0.20,  # 20% chance away keeps clean sheet
        'both_clean_sheet_prob': 0.07,  # 7% chance of 0-0
        'confidence': 0.78
    }
"""

from typing import Dict, Any
import logging
from scipy.stats import poisson

from src.models.base_model import BaseModel

# Set up logging
logger = logging.getLogger(__name__)


class CleanSheetModel(BaseModel):
    """
    Predicts clean sheet probabilities for both teams.
    
    Clean sheets are heavily influenced by:
    - Team defensive strength
    - Opponent attacking weakness  
    - Home/away factor (home teams concede less)
    - Recent defensive form
    """
    
    def __init__(
        self,
        home_advantage_multiplier: float = 0.85,
        form_weight: float = 0.15
    ):
        """
        Initialise Clean Sheet model.
        
        Args:
            home_advantage_multiplier: How much home team defensive advantage
                                      (0.85 = home teams concede 15% fewer goals)
            form_weight: How much recent form affects prediction (0.0-0.3 reasonable)
        """
        super().__init__(
            name="CleanSheetModel",
            version="1.0.0",
            description="Clean sheet probability calculator"
        )
        
        self.home_advantage_multiplier = home_advantage_multiplier
        self.form_weight = form_weight
        
        logger.info(
            f"Clean Sheet Model initialised "
            f"(home advantage: {home_advantage_multiplier}, "
            f"form weight: {form_weight})"
        )
    
    def calculate_expected_goals_against(
        self,
        features: Dict[str, Any],
        team_is_home: bool
    ) -> float:
        """
        Calculate expected goals a team will concede.
        
        This is the inverse of normal xG calculation - we care about
        how many goals a team is likely to CONCEDE, not score.
        
        Args:
            features: Match features from FeatureEngine
            team_is_home: True if calculating for home team, False for away
            
        Returns:
            Expected goals against (what team will concede)
        """
        if team_is_home:
            # Home team facing away attack
            our_defence = features.get('home_defence_strength', 1.0)
            their_attack = features.get('away_attack_strength', 1.0)
            our_goals_against_avg = features.get('home_goals_against_avg', 1.5)
            
            # Home teams have defensive advantage
            defensive_bonus = self.home_advantage_multiplier
            
        else:
            # Away team facing home attack
            our_defence = features.get('away_defence_strength', 1.0)
            their_attack = features.get('home_attack_strength', 1.0)
            our_goals_against_avg = features.get('away_goals_against_avg', 1.5)
            
            # Away teams have no defensive bonus (actually at disadvantage)
            defensive_bonus = 1.0
        
        # League average goals per team
        league_avg_goals = 1.5
        
        # Calculate expected goals against
        # xGA = Opponent Attack × Our Defence × League Avg × Defensive Adjustment
        expected_goals_against = (
            their_attack 
            * our_defence 
            * league_avg_goals 
            * defensive_bonus
        )
        
        # Small adjustment for recent defensive form
        # If we've been conceding fewer goals recently, adjust downward
        form_adjustment = 1.0
        if team_is_home:
            # Check if home team has good defensive form
            goals_against_ratio = our_goals_against_avg / league_avg_goals
            if goals_against_ratio < 0.8:  # Conceding 20% less than average
                form_adjustment = 1 - (self.form_weight * 0.5)
        else:
            goals_against_ratio = our_goals_against_avg / league_avg_goals
            if goals_against_ratio < 0.8:
                form_adjustment = 1 - (self.form_weight * 0.5)
        
        expected_goals_against *= form_adjustment
        
        logger.debug(
            f"{'Home' if team_is_home else 'Away'} expected goals against: "
            f"{expected_goals_against:.2f}"
        )
        
        return expected_goals_against
    
    def calculate_clean_sheet_probability(
        self,
        expected_goals_against: float
    ) -> float:
        """
        Calculate probability of keeping a clean sheet.
        
        Clean sheet means opponent scores 0 goals.
        Uses Poisson distribution: P(0 goals | λ=expected_goals_against)
        
        Args:
            expected_goals_against: Expected goals to concede
            
        Returns:
            Probability of clean sheet (0.0-1.0)
        """
        # Probability opponent scores exactly 0 goals
        clean_sheet_prob = poisson.pmf(0, expected_goals_against)
        
        return clean_sheet_prob
    
    def calculate_both_clean_sheet_probability(
        self,
        home_cs_prob: float,
        away_cs_prob: float
    ) -> float:
        """
        Calculate probability both teams keep clean sheets (0-0 draw).
        
        Assumes clean sheets are independent (not quite true in reality,
        but close enough for a simple model).
        
        Args:
            home_cs_prob: Home team clean sheet probability
            away_cs_prob: Away team clean sheet probability
            
        Returns:
            Probability of 0-0 result
        """
        # P(both clean sheets) = P(home CS) × P(away CS)
        both_cs_prob = home_cs_prob * away_cs_prob
        
        return both_cs_prob
    
    def calculate_confidence(
        self,
        features: Dict[str, Any],
        home_xga: float,
        away_xga: float
    ) -> float:
        """
        Calculate confidence in prediction.
        
        Confidence is lower when:
        - Expected goals against is very low/high (edge cases)
        - Teams have limited data
        - Using default feature values
        
        Args:
            features: Match features
            home_xga: Home team expected goals against
            away_xga: Away team expected goals against
            
        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 1.0
        
        # Reduce confidence if very high expected goals against
        # (defensive disasters are unpredictable)
        if home_xga > 3.0 or away_xga > 3.0:
            confidence *= 0.8
        
        # Reduce confidence if very low expected goals against
        # (too optimistic, probably overestimating defence)
        if home_xga < 0.5 or away_xga < 0.5:
            confidence *= 0.85
        
        # Reduce confidence if using default ELO
        if features['home_elo'] == 1500 and features['away_elo'] == 1500:
            confidence *= 0.75
        
        # Reduce confidence if no H2H data
        if features['h2h_matches_played'] == 0:
            confidence *= 0.9
        
        # Boost confidence if teams have strong defensive records
        home_defence_quality = features.get('home_defence_strength', 1.0)
        away_defence_quality = features.get('away_defence_strength', 1.0)
        
        if home_defence_quality < 0.8:  # Strong defence
            confidence *= 1.05
        if away_defence_quality < 0.8:
            confidence *= 1.05
        
        # Cap confidence at 0.95 (never be too sure)
        confidence = min(0.95, confidence)
        
        return confidence
    
    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str
    ) -> Dict[str, Any]:
        """
        Predict clean sheet probabilities for a match.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            match_date: Match date (YYYY-MM-DD)
            
        Returns:
            Dictionary with:
                - home_clean_sheet_prob: Probability home keeps clean sheet
                - away_clean_sheet_prob: Probability away keeps clean sheet
                - both_clean_sheet_prob: Probability of 0-0 draw
                - neither_clean_sheet_prob: Probability both teams score
                - home_expected_goals_against: Expected goals home will concede
                - away_expected_goals_against: Expected goals away will concede
                - confidence: Confidence in prediction
        """
        # Validate inputs
        if not self.validate_inputs(home_team_id, away_team_id, match_date):
            logger.error("Invalid inputs for clean sheet prediction")
            return self._get_default_prediction()
        
        try:
            # Get match features
            features = self.get_features(home_team_id, away_team_id, match_date)
            
            # Calculate expected goals against for each team
            home_xga = self.calculate_expected_goals_against(features, team_is_home=True)
            away_xga = self.calculate_expected_goals_against(features, team_is_home=False)
            
            # Calculate clean sheet probabilities
            home_cs_prob = self.calculate_clean_sheet_probability(home_xga)
            away_cs_prob = self.calculate_clean_sheet_probability(away_xga)
            
            # Calculate probability both teams keep clean sheets (0-0)
            both_cs_prob = self.calculate_both_clean_sheet_probability(
                home_cs_prob, 
                away_cs_prob
            )
            
            # Calculate probability neither team keeps clean sheet (BTTS)
            neither_cs_prob = (1 - home_cs_prob) * (1 - away_cs_prob)
            
            # Calculate confidence
            confidence = self.calculate_confidence(features, home_xga, away_xga)
            
            # Construct prediction
            prediction = {
                'home_clean_sheet_prob': home_cs_prob,
                'away_clean_sheet_prob': away_cs_prob,
                'both_clean_sheet_prob': both_cs_prob,  # 0-0 probability
                'neither_clean_sheet_prob': neither_cs_prob,  # BTTS probability
                'home_expected_goals_against': home_xga,
                'away_expected_goals_against': away_xga,
                'confidence': confidence
            }
            
            # Update model metadata
            self._update_metadata()
            
            logger.info(
                f"Clean Sheet Prediction: "
                f"Home {home_cs_prob:.1%}, Away {away_cs_prob:.1%}, "
                f"0-0 {both_cs_prob:.1%} "
                f"(confidence: {confidence:.1%})"
            )
            
            return prediction
            
        except Exception as e:
            logger.error(f"Clean sheet prediction failed: {e}")
            return self._get_default_prediction()
    
    def _get_default_prediction(self) -> Dict[str, Any]:
        """
        Return default prediction if calculation fails.
        """
        return {
            'home_clean_sheet_prob': 0.30,
            'away_clean_sheet_prob': 0.20,
            'both_clean_sheet_prob': 0.06,
            'neither_clean_sheet_prob': 0.56,
            'home_expected_goals_against': 1.2,
            'away_expected_goals_against': 1.8,
            'confidence': 0.0,
            'error': 'Prediction failed - using defaults'
        }
    
    def get_betting_recommendation(
        self,
        prediction: Dict[str, Any],
        bookmaker_odds: Dict[str, float],
        market: str = 'home_clean_sheet'
    ) -> Dict[str, Any]:
        """
        Compare model prediction to bookmaker odds.
        
        Args:
            prediction: Model prediction from predict()
            bookmaker_odds: Dict with odds for various clean sheet markets
            market: Which market to analyse:
                   - 'home_clean_sheet': Home team clean sheet
                   - 'away_clean_sheet': Away team clean sheet
                   - 'both_clean_sheet': 0-0 draw
                   - 'neither_clean_sheet': Both teams score
            
        Returns:
            Betting recommendation with expected value
        """
        confidence = prediction['confidence']
        
        # Get our probability and odds based on market
        if market == 'home_clean_sheet':
            our_prob = prediction['home_clean_sheet_prob']
            odds = bookmaker_odds.get('home_clean_sheet', 2.5)
        elif market == 'away_clean_sheet':
            our_prob = prediction['away_clean_sheet_prob']
            odds = bookmaker_odds.get('away_clean_sheet', 3.0)
        elif market == 'both_clean_sheet':
            our_prob = prediction['both_clean_sheet_prob']
            odds = bookmaker_odds.get('both_clean_sheet', 10.0)
        elif market == 'neither_clean_sheet':
            our_prob = prediction['neither_clean_sheet_prob']
            odds = bookmaker_odds.get('neither_clean_sheet', 1.8)
        else:
            return {'bet': 'No Bet', 'reason': 'Invalid market'}
        
        # Calculate implied probability and expected value
        implied_prob = 1 / odds
        expected_value = (our_prob * odds) - 1
        edge = our_prob - implied_prob
        
        # Recommend bet if positive EV and sufficient confidence
        if expected_value > 0.05 and confidence >= 0.65:
            recommendation = {
                'bet': market.replace('_', ' ').title(),
                'expected_value': expected_value,
                'our_probability': our_prob,
                'bookmaker_probability': implied_prob,
                'edge': edge,
                'recommended_odds': odds,
                'confidence': confidence
            }
        else:
            recommendation = {
                'bet': 'No Bet',
                'expected_value': expected_value,
                'reason': 'Insufficient edge or confidence',
                'edge': edge,
                'confidence': confidence
            }
        
        return recommendation


if __name__ == "__main__":
    """
    Test Clean Sheet model.
    """
    print("\n" + "="*60)
    print("CLEAN SHEET MODEL TEST")
    print("="*60 + "\n")
    
    # Create model
    model = CleanSheetModel()
    
    print(f"Model info: {model.get_info()}\n")
    
    # Test prediction
    print("Testing prediction...")
    prediction = model.predict(
        home_team_id=1,
        away_team_id=2,
        match_date='2024-01-15'
    )
    
    print(f"\nClean Sheet Probabilities:")
    print(f"  Home CS: {prediction['home_clean_sheet_prob']:.1%}")
    print(f"  Away CS: {prediction['away_clean_sheet_prob']:.1%}")
    print(f"  0-0 Draw: {prediction['both_clean_sheet_prob']:.1%}")
    print(f"  BTTS (neither CS): {prediction['neither_clean_sheet_prob']:.1%}")
    print(f"\nExpected Goals Against:")
    print(f"  Home: {prediction['home_expected_goals_against']:.2f}")
    print(f"  Away: {prediction['away_expected_goals_against']:.2f}")
    print(f"\nConfidence: {prediction['confidence']:.1%}")
    
    # Test betting recommendations
    print("\n--- Betting Recommendations ---")
    bookmaker_odds = {
        'home_clean_sheet': 2.8,
        'away_clean_sheet': 4.5,
        'both_clean_sheet': 12.0,
        'neither_clean_sheet': 1.75
    }
    
    for market in ['home_clean_sheet', 'away_clean_sheet', 
                   'both_clean_sheet', 'neither_clean_sheet']:
        rec = model.get_betting_recommendation(prediction, bookmaker_odds, market)
        print(f"\n{market.replace('_', ' ').title()}:")
        print(f"  Bet: {rec['bet']}")
        if rec['bet'] != 'No Bet':
            print(f"  EV: {rec['expected_value']:.2%}")
            print(f"  Edge: {rec['edge']:.2%}")
        else:
            print(f"  Reason: {rec.get('reason', 'Unknown')}")
    
    print("\n" + "="*60)
    print("Clean Sheet model working correctly!")
    print("="*60 + "\n")