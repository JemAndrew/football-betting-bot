"""
Referee Profiler

Tracks referee statistics and tendencies.

Key metrics:
- Cards per game (yellow/red)
- Penalty frequency
- Fouls called per game
- Corners per game (some refs call more fouls = more corners)
- Home bias (do they favour home teams?)
- Consistency (variance in decisions)

Usage:
    profiler = RefereeProfiler()
    profile = profiler.get_referee_profile(referee_id=1)
    if profile['card_rate'] > 4.5:
        print("Card-happy ref - expect disrupted play")
"""

from typing import Dict, Optional, List
from datetime import datetime
import logging

from src.data.database import Session, Match
from sqlalchemy import func

logger = logging.getLogger(__name__)


class RefereeProfiler:
    """
    Creates profiles of referee tendencies.
    
    Critical for cards and corners predictions.
    """
    
    def __init__(self, min_matches: int = 10):
        """
        Initialise referee profiler.
        
        Args:
            min_matches: Minimum matches for reliable statistics
        """
        self.min_matches = min_matches
        logger.info(f"Referee Profiler initialised: min_matches={min_matches}")
    
    def get_referee_profile(
        self,
        referee_id: int,
        lookback_matches: Optional[int] = 50
    ) -> Dict:
        """
        Get comprehensive referee profile.
        
        Args:
            referee_id: Referee to profile
            lookback_matches: Number of recent matches to analyse
            
        Returns:
            {
                'referee_id': 1,
                'referee_name': 'Michael Oliver',
                'matches_officiated': 127,
                'avg_cards_per_game': 3.8,
                'avg_yellow_cards': 3.5,
                'avg_red_cards': 0.3,
                'avg_penalties_per_game': 0.25,
                'avg_fouls_per_game': 24.5,
                'avg_corners_per_game': 10.2,
                'strictness': 'average',  # lenient, average, strict
                'card_tendency': 'moderate',  # low, moderate, high
                'home_bias': 1.05,  # Ratio of home/away decisions
                'consistency': 0.82,  # 0-1, higher = more consistent
                'penalty_rate': 'average',  # low, average, high
                'affects_cards_market': True,
                'affects_corners_market': False
            }
        """
        session = Session()
        
        try:
            # NOTE: This implementation assumes you have referee data
            # If referee_id field doesn't exist yet, this returns placeholder
            
            # Get referee's recent matches
            # TODO: Replace with actual referee query when field exists
            matches = session.query(Match).limit(lookback_matches).all()
            
            if len(matches) < self.min_matches:
                logger.warning(f"Insufficient data for referee {referee_id}")
                return self._empty_profile(referee_id)
            
            # Calculate statistics
            # NOTE: These calculations assume match has referee_id and card/corner fields
            # Current DB may not have these - this is preparation for Phase 6
            
            total_matches = len(matches)
            
            # Cards statistics (from match.home_cards + match.away_cards)
            # Currently NULL in DB - placeholder calculation
            total_cards = 0
            total_yellows = 0
            total_reds = 0
            
            # Corners statistics (from match.home_corners + match.away_corners)
            # Currently NULL in DB
            total_corners = 0
            
            # Fouls and penalties (not tracked yet)
            # These would come from detailed match data
            
            # For now, return estimated profile
            # TODO: Update when referee data available
            avg_cards = 3.8  # League average
            avg_corners = 10.5  # League average
            
            strictness = self._classify_strictness(avg_cards)
            card_tendency = self._classify_card_tendency(avg_cards)
            
            return {
                'referee_id': referee_id,
                'referee_name': f'Referee {referee_id}',  # TODO: Get actual name
                'matches_officiated': total_matches,
                'avg_cards_per_game': avg_cards,
                'avg_yellow_cards': avg_cards * 0.9,  # ~90% are yellows
                'avg_red_cards': avg_cards * 0.1,  # ~10% are reds
                'avg_penalties_per_game': 0.25,  # League average
                'avg_fouls_per_game': 24.0,  # Typical
                'avg_corners_per_game': avg_corners,
                'strictness': strictness,
                'card_tendency': card_tendency,
                'home_bias': 1.0,  # Neutral until calculated
                'consistency': 0.75,  # Placeholder
                'penalty_rate': 'average',
                'affects_cards_market': abs(avg_cards - 3.8) > 0.5,
                'affects_corners_market': abs(avg_corners - 10.5) > 1.0,
                'data_available': False,  # Set to True when real data exists
                'note': 'Using placeholder data - referee tracking not yet implemented'
            }
            
        except Exception as e:
            logger.error(f"Error profiling referee: {e}")
            return self._empty_profile(referee_id)
        finally:
            session.close()
    
    def _classify_strictness(self, avg_cards: float) -> str:
        """
        Classify referee strictness.
        
        Based on cards per game:
        - <3.0 = lenient
        - 3.0-4.5 = average
        - >4.5 = strict
        """
        if avg_cards < 3.0:
            return 'lenient'
        elif avg_cards <= 4.5:
            return 'average'
        else:
            return 'strict'
    
    def _classify_card_tendency(self, avg_cards: float) -> str:
        """Classify card tendency (low/moderate/high)."""
        if avg_cards < 3.2:
            return 'low'
        elif avg_cards <= 4.2:
            return 'moderate'
        else:
            return 'high'
    
    def get_referee_comparison(
        self,
        referee_id: int,
        league_avg: Optional[Dict] = None
    ) -> Dict:
        """
        Compare referee to league average.
        
        Args:
            referee_id: Referee to analyse
            league_avg: League averages (if None, uses defaults)
            
        Returns:
            Comparison metrics vs league average
        """
        if league_avg is None:
            league_avg = {
                'cards': 3.8,
                'corners': 10.5,
                'penalties': 0.25
            }
        
        profile = self.get_referee_profile(referee_id)
        
        return {
            'cards_vs_avg': profile['avg_cards_per_game'] - league_avg['cards'],
            'corners_vs_avg': profile['avg_corners_per_game'] - league_avg['corners'],
            'penalties_vs_avg': profile['avg_penalties_per_game'] - league_avg['penalties'],
            'above_avg_cards': profile['avg_cards_per_game'] > league_avg['cards'],
            'above_avg_corners': profile['avg_corners_per_game'] > league_avg['corners'],
            'card_multiplier': profile['avg_cards_per_game'] / league_avg['cards']
        }
    
    def get_top_card_referees(self, limit: int = 5) -> List[Dict]:
        """
        Get referees who show most cards.
        
        Useful for identifying which refs affect cards market most.
        """
        # TODO: Implement when referee data available
        return []
    
    def _empty_profile(self, referee_id: int) -> Dict:
        """Return empty profile."""
        return {
            'referee_id': referee_id,
            'referee_name': f'Unknown Referee {referee_id}',
            'matches_officiated': 0,
            'avg_cards_per_game': 3.8,  # League average
            'avg_yellow_cards': 3.4,
            'avg_red_cards': 0.4,
            'avg_penalties_per_game': 0.25,
            'avg_fouls_per_game': 24.0,
            'avg_corners_per_game': 10.5,
            'strictness': 'average',
            'card_tendency': 'moderate',
            'home_bias': 1.0,
            'consistency': 0.75,
            'penalty_rate': 'average',
            'affects_cards_market': False,
            'affects_corners_market': False,
            'data_available': False,
            'note': 'Insufficient data for referee profile'
        }


# TODO: When referee data becomes available, add this function
def add_referee_to_database(referee_name: str, referee_external_id: int):
    """
    Add referee to database for tracking.
    
    This is preparation for Phase 6 when you collect referee data.
    """
    # Would create referees table and store:
    # - referee_id, name, external_id
    # - avg_cards, avg_corners, avg_penalties
    # - Calculate from historical matches
    pass


if __name__ == '__main__':
    """Quick test."""
    print("Referee Profiler Test\n")
    
    profiler = RefereeProfiler()
    
    # Test with placeholder referee
    profile = profiler.get_referee_profile(referee_id=1)
    
    print(f"Referee: {profile['referee_name']}")
    print(f"Matches: {profile['matches_officiated']}")
    print(f"Avg Cards: {profile['avg_cards_per_game']:.2f}")
    print(f"Avg Corners: {profile['avg_corners_per_game']:.2f}")
    print(f"Strictness: {profile['strictness']}")
    print(f"Card Tendency: {profile['card_tendency']}")
    print(f"\nNote: {profile['note']}")
    
    print("\nReferee Profiler working correctly (with placeholder data)")
    print("TODO: Implement referee tracking in Phase 6")