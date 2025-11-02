"""
Data validation functions for the betting bot.

Ensures data integrity and catches errors early.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import re


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_odds(
    odds: float,
    min_odds: float = 1.01,
    max_odds: float = 100.0,
) -> bool:
    """
    Validate that odds are within reasonable bounds.
    
    Args:
        odds: Odds value to validate
        min_odds: Minimum acceptable odds
        max_odds: Maximum acceptable odds
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If odds are invalid
    """
    if not isinstance(odds, (int, float)):
        raise ValidationError(f"Odds must be numeric, got {type(odds)}")
    
    if odds < min_odds:
        raise ValidationError(f"Odds {odds} below minimum {min_odds}")
    
    if odds > max_odds:
        raise ValidationError(f"Odds {odds} above maximum {max_odds}")
    
    return True


def validate_probability(prob: float) -> bool:
    """
    Validate that a probability is between 0 and 1.
    
    Args:
        prob: Probability to validate
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If probability is invalid
    """
    if not isinstance(prob, (int, float)):
        raise ValidationError(f"Probability must be numeric, got {type(prob)}")
    
    if not 0 <= prob <= 1:
        raise ValidationError(f"Probability {prob} must be between 0 and 1")
    
    return True


def validate_score(score: int, max_score: int = 20) -> bool:
    """
    Validate that a match score is reasonable.
    
    Args:
        score: Score to validate
        max_score: Maximum reasonable score
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If score is invalid
    """
    if not isinstance(score, int):
        raise ValidationError(f"Score must be an integer, got {type(score)}")
    
    if score < 0:
        raise ValidationError(f"Score cannot be negative: {score}")
    
    if score > max_score:
        raise ValidationError(
            f"Score {score} exceeds maximum {max_score} - possible data error"
        )
    
    return True


def validate_date(
    date: Any,
    min_date: Optional[datetime] = None,
    max_date: Optional[datetime] = None,
) -> bool:
    """
    Validate that a date is in the correct format and range.
    
    Args:
        date: Date to validate (string or datetime)
        min_date: Minimum acceptable date
        max_date: Maximum acceptable date
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If date is invalid
    """
    # Convert string to datetime if needed
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValidationError(f"Invalid date format: {date}. Expected YYYY-MM-DD")
    
    if not isinstance(date, datetime):
        raise ValidationError(f"Date must be string or datetime, got {type(date)}")
    
    # Check date range
    if min_date and date < min_date:
        raise ValidationError(f"Date {date} before minimum {min_date}")
    
    if max_date and date > max_date:
        raise ValidationError(f"Date {date} after maximum {max_date}")
    
    return True


def validate_match_data(match_data: Dict[str, Any]) -> bool:
    """
    Validate a complete match data dictionary.
    
    Args:
        match_data: Dictionary containing match information
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If any field is invalid
    """
    required_fields = [
        "date",
        "home_team_id",
        "away_team_id",
        "league_id",
    ]
    
    # Check required fields exist
    for field in required_fields:
        if field not in match_data:
            raise ValidationError(f"Missing required field: {field}")
    
    # Validate date
    validate_date(match_data["date"])
    
    # Validate team IDs are different
    if match_data["home_team_id"] == match_data["away_team_id"]:
        raise ValidationError("Home and away team cannot be the same")
    
    # Validate scores if present
    if "home_goals" in match_data:
        validate_score(match_data["home_goals"])
    
    if "away_goals" in match_data:
        validate_score(match_data["away_goals"])
    
    # Validate corners if present
    if "home_corners" in match_data:
        validate_score(match_data["home_corners"], max_score=30)
    
    if "away_corners" in match_data:
        validate_score(match_data["away_corners"], max_score=30)
    
    # Validate cards if present
    if "home_cards" in match_data:
        validate_score(match_data["home_cards"], max_score=15)
    
    if "away_cards" in match_data:
        validate_score(match_data["away_cards"], max_score=15)
    
    return True


def validate_stake(
    stake: float,
    bankroll: float,
    max_stake_pct: float = 0.05,
) -> bool:
    """
    Validate that a stake is appropriate given bankroll.
    
    Args:
        stake: Stake amount
        bankroll: Current bankroll
        max_stake_pct: Maximum stake as percentage of bankroll
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If stake is invalid
    """
    if not isinstance(stake, (int, float)):
        raise ValidationError(f"Stake must be numeric, got {type(stake)}")
    
    if stake <= 0:
        raise ValidationError(f"Stake must be positive, got {stake}")
    
    if stake > bankroll:
        raise ValidationError(
            f"Stake £{stake:.2f} exceeds bankroll £{bankroll:.2f}"
        )
    
    max_stake = bankroll * max_stake_pct
    if stake > max_stake:
        raise ValidationError(
            f"Stake £{stake:.2f} exceeds maximum £{max_stake:.2f} "
            f"({max_stake_pct:.1%} of bankroll)"
        )
    
    return True


def validate_elo_rating(elo: float, min_elo: float = 1000, max_elo: float = 2500) -> bool:
    """
    Validate an ELO rating is within reasonable bounds.
    
    Args:
        elo: ELO rating to validate
        min_elo: Minimum reasonable ELO
        max_elo: Maximum reasonable ELO
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If ELO is invalid
    """
    if not isinstance(elo, (int, float)):
        raise ValidationError(f"ELO must be numeric, got {type(elo)}")
    
    if elo < min_elo or elo > max_elo:
        raise ValidationError(
            f"ELO {elo} outside reasonable range [{min_elo}, {max_elo}]"
        )
    
    return True


def validate_form_points(points: int, max_points: int = 15) -> bool:
    """
    Validate form points (typically from last 5 games).
    
    Args:
        points: Form points to validate
        max_points: Maximum possible points (5 wins = 15 points)
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If form points are invalid
    """
    if not isinstance(points, int):
        raise ValidationError(f"Form points must be integer, got {type(points)}")
    
    if points < 0:
        raise ValidationError(f"Form points cannot be negative: {points}")
    
    if points > max_points:
        raise ValidationError(
            f"Form points {points} exceed maximum {max_points}"
        )
    
    return True


def validate_api_key(api_key: str, min_length: int = 10) -> bool:
    """
    Validate that an API key looks reasonable.
    
    Args:
        api_key: API key to validate
        min_length: Minimum expected length
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If API key is invalid
    """
    if not isinstance(api_key, str):
        raise ValidationError(f"API key must be string, got {type(api_key)}")
    
    if len(api_key) < min_length:
        raise ValidationError(
            f"API key too short (length {len(api_key)}, expected ≥{min_length})"
        )
    
    if api_key.lower() in ["none", "null", "your_key_here", ""]:
        raise ValidationError("API key not set properly")
    
    return True


def validate_team_name(name: str) -> bool:
    """
    Validate a team name is reasonable.
    
    Args:
        name: Team name to validate
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If team name is invalid
    """
    if not isinstance(name, str):
        raise ValidationError(f"Team name must be string, got {type(name)}")
    
    if len(name) < 3:
        raise ValidationError(f"Team name too short: '{name}'")
    
    if len(name) > 50:
        raise ValidationError(f"Team name too long: '{name}'")
    
    return True


def validate_league_id(league_id: str, valid_leagues: Optional[List[str]] = None) -> bool:
    """
    Validate a league ID.
    
    Args:
        league_id: League ID to validate
        valid_leagues: List of valid league IDs
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If league ID is invalid
    """
    if not isinstance(league_id, str):
        raise ValidationError(f"League ID must be string, got {type(league_id)}")
    
    if valid_leagues and league_id not in valid_leagues:
        raise ValidationError(
            f"Unknown league ID: {league_id}. Valid leagues: {valid_leagues}"
        )
    
    return True


def validate_prediction(prediction: Dict[str, Any]) -> bool:
    """
    Validate a model prediction dictionary.
    
    Args:
        prediction: Prediction dictionary
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If prediction is invalid
    """
    required_fields = ["match_id", "model_name", "predicted_prob", "confidence"]
    
    for field in required_fields:
        if field not in prediction:
            raise ValidationError(f"Missing required field in prediction: {field}")
    
    # Validate probability
    validate_probability(prediction["predicted_prob"])
    
    # Validate confidence (also a probability)
    validate_probability(prediction["confidence"])
    
    return True


def safe_validate(validator_func, *args, **kwargs) -> tuple[bool, Optional[str]]:
    """
    Safely run a validator and return result without raising.
    
    Args:
        validator_func: Validation function to run
        *args: Arguments for validator
        **kwargs: Keyword arguments for validator
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        validator_func(*args, **kwargs)
        return True, None
    except ValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected validation error: {str(e)}"


# Example usage
if __name__ == "__main__":
    # Test validators
    try:
        validate_odds(2.5)
        print("✓ Valid odds")
    except ValidationError as e:
        print(f"✗ {e}")
    
    try:
        validate_odds(150.0)  # Should fail
    except ValidationError as e:
        print(f"✓ Caught invalid odds: {e}")
    
    try:
        validate_probability(0.65)
        print("✓ Valid probability")
    except ValidationError as e:
        print(f"✗ {e}")
    
    try:
        validate_score(3)
        print("✓ Valid score")
    except ValidationError as e:
        print(f"✗ {e}")
    
    # Test match data validation
    match_data = {
        "date": "2024-01-15",
        "home_team_id": 1,
        "away_team_id": 2,
        "league_id": "PL",
        "home_goals": 2,
        "away_goals": 1,
    }
    
    try:
        validate_match_data(match_data)
        print("✓ Valid match data")
    except ValidationError as e:
        print(f"✗ {e}")