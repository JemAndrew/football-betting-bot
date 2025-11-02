"""
Constants used throughout the betting bot.

This module contains all hardcoded values like league IDs, market types,
team mappings, and other configuration constants.
"""

from enum import Enum
from typing import Dict


class League(Enum):
    """Football league identifiers."""
    PREMIER_LEAGUE = "PL"
    LA_LIGA = "PD"
    BUNDESLIGA = "BL1"
    SERIE_A = "SA"
    LIGUE_1 = "FL1"
    CHAMPIONSHIP = "ELC"
    EREDIVISIE = "DED"


class Market(Enum):
    """Betting market types."""
    OVER_UNDER_25 = "over_under_2_5"
    BTTS = "btts"
    MATCH_RESULT = "match_result"
    TOTAL_CORNERS = "total_corners"
    TOTAL_CARDS = "total_cards"


# League configurations
LEAGUE_CONFIG: Dict[str, Dict] = {
    "PL": {
        "name": "Premier League",
        "country": "England",
        "football_data_id": 2021,
        "avg_goals": 2.82,
        "home_advantage": 0.35,
    },
    "PD": {
        "name": "La Liga",
        "country": "Spain", 
        "football_data_id": 2014,
        "avg_goals": 2.68,
        "home_advantage": 0.32,
    },
    "BL1": {
        "name": "Bundesliga",
        "country": "Germany",
        "football_data_id": 2002,
        "avg_goals": 3.15,
        "home_advantage": 0.30,
    },
    "SA": {
        "name": "Serie A",
        "country": "Italy",
        "football_data_id": 2019,
        "avg_goals": 2.95,
        "home_advantage": 0.28,
    },
    "FL1": {
        "name": "Ligue 1",
        "country": "France",
        "football_data_id": 2015,
        "avg_goals": 2.71,
        "home_advantage": 0.31,
    },
}

# ELO rating constants
ELO_CONFIG = {
    "initial_rating": 1500,
    "k_factor": 20,
    "k_factor_playoffs": 30,
    "home_advantage": 100,
}

# Form calculation constants
FORM_CONFIG = {
    "games_lookback": 5,
    "decay_factor": 0.95,  # Exponential decay for older games
    "win_points": 3,
    "draw_points": 1,
    "loss_points": 0,
}

# Betting constraints
BETTING_CONFIG = {
    "min_odds": 1.5,
    "max_odds": 5.0,
    "min_edge": 0.05,  # 5% minimum edge
    "max_stake_pct": 0.05,  # 5% of bankroll
    "kelly_fraction": 0.25,  # Quarter Kelly for safety
}

# API rate limits (requests per minute)
API_RATE_LIMITS = {
    "football_data": 10,
    "odds_api": 60,
    "sportmonks": 3000,  # Premium tier
}

# Database table names
DB_TABLES = {
    "matches": "matches",
    "teams": "teams",
    "odds": "odds",
    "predictions": "predictions",
    "bets": "bets",
    "referees": "referees",
}

# Match status
class MatchStatus(Enum):
    """Match status codes."""
    SCHEDULED = "SCHEDULED"
    LIVE = "IN_PLAY"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"


# Odds formats
class OddsFormat(Enum):
    """Odds format types."""
    DECIMAL = "decimal"
    FRACTIONAL = "fractional"
    AMERICAN = "american"


# Model types
class ModelType(Enum):
    """Machine learning model types."""
    POISSON = "poisson"
    XGBOOST = "xgboost"
    ENSEMBLE = "ensemble"


# Feature groups for ML
FEATURE_GROUPS = {
    "elo": ["home_elo", "away_elo", "elo_diff"],
    "form": ["home_form", "away_form", "form_diff"],
    "goals": ["home_goals_for", "home_goals_against", "away_goals_for", "away_goals_against"],
    "corners": ["home_corners_for", "home_corners_against", "away_corners_for", "away_corners_against"],
    "cards": ["home_cards_for", "home_cards_against", "away_cards_for", "away_cards_against"],
    "match": ["days_rest_home", "days_rest_away", "h2h_home_wins", "h2h_away_wins"],
}

# Paths
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
MODELS_DIR = os.path.join(BASE_DIR, "models")
CONFIG_DIR = os.path.join(BASE_DIR, "config")