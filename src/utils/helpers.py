"""
Helper utility functions used throughout the betting bot.

Contains functions for date manipulation, odds conversion, data formatting,
and other common operations.
"""

from datetime import datetime, timedelta
from typing import Union, Optional, List, Dict, Any
import numpy as np


def convert_odds(
    odds: float,
    from_format: str = "decimal",
    to_format: str = "probability"
) -> float:
    """
    Convert odds between different formats.
    
    Args:
        odds: The odds value to convert
        from_format: Source format ('decimal', 'fractional', 'american')
        to_format: Target format ('decimal', 'fractional', 'american', 'probability')
    
    Returns:
        Converted odds value
    
    Examples:
        >>> convert_odds(2.0, 'decimal', 'probability')
        0.5
        >>> convert_odds(2.0, 'decimal', 'american')
        100.0
    """
    # First convert to decimal if not already
    if from_format == "decimal":
        decimal_odds = odds
    elif from_format == "fractional":
        decimal_odds = odds + 1
    elif from_format == "american":
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1
    else:
        raise ValueError(f"Unknown from_format: {from_format}")
    
    # Now convert to target format
    if to_format == "decimal":
        return decimal_odds
    elif to_format == "probability":
        return 1 / decimal_odds
    elif to_format == "fractional":
        return decimal_odds - 1
    elif to_format == "american":
        if decimal_odds >= 2:
            return (decimal_odds - 1) * 100
        else:
            return -100 / (decimal_odds - 1)
    else:
        raise ValueError(f"Unknown to_format: {to_format}")


def implied_probability(odds: float) -> float:
    """
    Calculate implied probability from decimal odds.
    
    Args:
        odds: Decimal odds
    
    Returns:
        Implied probability (0 to 1)
    
    Example:
        >>> implied_probability(2.0)
        0.5
    """
    return 1 / odds


def calculate_overround(odds_list: List[float]) -> float:
    """
    Calculate bookmaker overround (margin) from a list of odds.
    
    Args:
        odds_list: List of decimal odds for all outcomes
    
    Returns:
        Overround as a percentage
    
    Example:
        >>> calculate_overround([2.1, 3.5, 3.8])  # Home, Draw, Away
        103.45
    """
    total_prob = sum(1/odds for odds in odds_list)
    return (total_prob - 1) * 100


def remove_overround(odds: float, total_prob: float) -> float:
    """
    Remove bookmaker overround to get fair odds.
    
    Args:
        odds: Decimal odds
        total_prob: Total implied probability of all outcomes
    
    Returns:
        Fair odds with overround removed
    """
    implied_prob = 1 / odds
    fair_prob = implied_prob / total_prob
    return 1 / fair_prob


def format_date(date: Union[str, datetime], format_str: str = "%Y-%m-%d") -> str:
    """
    Format a date consistently.
    
    Args:
        date: Date as string or datetime object
        format_str: Desired output format
    
    Returns:
        Formatted date string
    """
    if isinstance(date, str):
        # Try parsing common formats
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                date = datetime.strptime(date, fmt)
                break
            except ValueError:
                continue
    
    if isinstance(date, datetime):
        return date.strftime(format_str)
    
    raise ValueError(f"Could not parse date: {date}")


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string into a datetime object.
    
    Args:
        date_str: Date string in various formats
    
    Returns:
        datetime object
    """
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse date string: {date_str}")


def days_between(date1: Union[str, datetime], date2: Union[str, datetime]) -> int:
    """
    Calculate days between two dates.
    
    Args:
        date1: First date
        date2: Second date
    
    Returns:
        Number of days between dates (can be negative)
    """
    if isinstance(date1, str):
        date1 = parse_date(date1)
    if isinstance(date2, str):
        date2 = parse_date(date2)
    
    return (date2 - date1).days


def calculate_edge(our_prob: float, odds: float) -> float:
    """
    Calculate betting edge.
    
    Args:
        our_prob: Our estimated probability
        odds: Bookmaker decimal odds
    
    Returns:
        Edge as a decimal (0.05 = 5% edge)
    """
    implied_prob = 1 / odds
    return our_prob - implied_prob


def calculate_expected_value(prob: float, odds: float) -> float:
    """
    Calculate expected value of a bet.
    
    Args:
        prob: Win probability (0 to 1)
        odds: Decimal odds
    
    Returns:
        Expected value as a percentage
    
    Example:
        >>> calculate_expected_value(0.6, 2.0)
        0.2  # 20% expected profit
    """
    return (prob * odds) - 1


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.
    
    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if denominator is zero
    
    Returns:
        Result of division or default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def standardise_team_name(name: str) -> str:
    """
    Standardise team names for consistent matching.
    
    Args:
        name: Team name
    
    Returns:
        Standardised team name
    
    Example:
        >>> standardise_team_name("Manchester United FC")
        "manchester united"
    """
    # Remove common suffixes
    name = name.replace(" FC", "").replace(" AFC", "").replace(" United", "")
    
    # Convert to lowercase and strip
    name = name.lower().strip()
    
    # Remove special characters
    name = "".join(c for c in name if c.isalnum() or c.isspace())
    
    return name


def exponential_decay_weights(n: int, decay_factor: float = 0.95) -> np.ndarray:
    """
    Generate exponential decay weights for time series data.
    
    Args:
        n: Number of data points
        decay_factor: Decay factor (0-1)
    
    Returns:
        Array of weights summing to 1
    
    Example:
        >>> exponential_decay_weights(5, 0.9)
        array([0.34, 0.31, 0.28, 0.25, 0.23])  # Most recent has highest weight
    """
    weights = np.array([decay_factor ** i for i in range(n)])
    return weights / weights.sum()


def is_valid_odds(odds: float, min_odds: float = 1.01, max_odds: float = 100.0) -> bool:
    """
    Check if odds are within valid range.
    
    Args:
        odds: Decimal odds to validate
        min_odds: Minimum valid odds
        max_odds: Maximum valid odds
    
    Returns:
        True if odds are valid
    """
    return min_odds <= odds <= max_odds


def round_stake(stake: float, precision: int = 2) -> float:
    """
    Round stake to specified precision.
    
    Args:
        stake: Stake amount
        precision: Decimal places
    
    Returns:
        Rounded stake
    """
    return round(stake, precision)


def get_season_from_date(date: datetime) -> str:
    """
    Get season string from a date (e.g., "2023/24").
    
    Football seasons typically run from August to May.
    
    Args:
        date: Date to extract season from
    
    Returns:
        Season string
    
    Example:
        >>> get_season_from_date(datetime(2023, 9, 15))
        "2023/24"
    """
    year = date.year
    if date.month >= 8:  # August onwards is new season
        return f"{year}/{str(year + 1)[2:]}"
    else:
        return f"{year - 1}/{str(year)[2:]}"


def calculate_form_points(results: List[str]) -> int:
    """
    Calculate form points from recent results.
    
    Args:
        results: List of results ('W', 'D', 'L') from oldest to newest
    
    Returns:
        Total form points
    
    Example:
        >>> calculate_form_points(['W', 'W', 'D', 'L', 'W'])
        10  # 3 + 3 + 1 + 0 + 3
    """
    points_map = {'W': 3, 'D': 1, 'L': 0}
    return sum(points_map.get(result, 0) for result in results)


def clip_value(value: float, min_val: float, max_val: float) -> float:
    """
    Clip a value to be within a range.
    
    Args:
        value: Value to clip
        min_val: Minimum allowed value
        max_val: Maximum allowed value
    
    Returns:
        Clipped value
    """
    return max(min_val, min(max_val, value))