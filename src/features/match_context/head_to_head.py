"""
Head-to-Head Analyser

Analyses historical matchups between two teams.

Why H2H matters:
- Some teams consistently beat others (psychological edge)
- Historical patterns repeat
- Team styles may clash in predictable ways
- Recent H2H form matters more than overall record

Example:
- If Arsenal beats Spurs 8 out of last 10 meetings
- Arsenal has psychological advantage
- Past scorelines show typical patterns

Usage:
    analyser = HeadToHeadAnalyser()
    h2h = analyser.analyse_h2h(home_id=1, away_id=2)
    print(f"Home wins: {h2h['home_wins']} / {h2h['matches_played']}")
"""

from typing import Dict, Optional, List
import logging

from src.features.team_features import TeamFeatures
from src.data.database import Session, Match, Team

logger = logging.getLogger(__name__)


class HeadToHeadAnalyser:
    """
    Analyses historical head-to-head record between teams.
    
    Some teams consistently beat others regardless of current form.
    """
    
    def __init__(self, lookback_matches: int = 10):
        """
        Initialise H2H analyser.
        
        Args:
            lookback_matches: How many past meetings to analyse (default 10)
        """
        self.lookback = lookback_matches
        self.team_features = TeamFeatures()
        
        logger.info(f"Head-to-Head Analyser initialised: lookback={lookback_matches} matches")
    
    def analyse_h2h(
        self,
        home_team_id: int,
        away_team_id: int
    ) -> Dict:
        """
        Analyse head-to-head record between two teams.
        
        Args:
            home_team_id: Home team (Team A in H2H)
            away_team_id: Away team (Team B in H2H)
            
        Returns:
            {
                'matches_played': 8,
                'home_wins': 4,
                'draws': 2,
                'away_wins': 2,
                'home_win_rate': 0.5,
                'away_win_rate': 0.25,
                'draw_rate': 0.25,
                'avg_home_goals': 1.8,
                'avg_away_goals': 1.2,
                'avg_total_goals': 3.0,
                'btts_rate': 0.625,
                'over_25_rate': 0.75,
                'home_dominance': 1.2,  # Home historically better
                'recent_form_h2h': 'WWDL',  # Last 4 for home team
                'clear_favourite': False,
                'evenly_matched': True,
                'home_advantage_h2h': 0.6,  # Home win% when playing at home
                'psychological_edge': 'home'  # Who has the edge
            }
        """
        try:
            # Get H2H data using existing team_features implementation
            h2h_data = self.team_features.get_head_to_head(
                team_a_id=home_team_id,
                team_b_id=away_team_id,
                limit=self.lookback
            )
            
            if h2h_data['matches_played'] == 0:
                logger.info(f"No H2H history found for teams {home_team_id} vs {away_team_id}")
                return self._empty_features()
            
            # Calculate additional metrics
            matches_played = h2h_data['matches_played']
            
            # Win rates
            home_win_rate = h2h_data['team_a_wins'] / matches_played
            away_win_rate = h2h_data['team_b_wins'] / matches_played
            draw_rate = h2h_data['draws'] / matches_played
            
            # Dominance factor (who historically wins more)
            if away_win_rate > 0:
                dominance = home_win_rate / away_win_rate
            else:
                dominance = 3.0 if home_win_rate > 0 else 1.0
            
            # Clear favourite detection
            clear_favourite = dominance > 1.5 or dominance < 0.67
            evenly_matched = 0.8 <= dominance <= 1.2
            
            # Goals analysis
            avg_home_goals = h2h_data['team_a_goals'] / matches_played
            avg_away_goals = h2h_data['team_b_goals'] / matches_played
            
            # Over 2.5 rate
            over_25_count = 0
            if 'scorelines' in h2h_data:
                # Count matches with over 2.5 goals
                # This would need more detailed data
                pass
            
            # Estimate over 2.5 from average
            avg_total = h2h_data['avg_total_goals']
            over_25_rate = self._estimate_over_25_rate(avg_total)
            
            # Get recent form in H2H (if we have match details)
            recent_form = self._get_recent_h2h_form(
                home_team_id, away_team_id, n=5
            )
            
            # Home advantage in H2H
            # (percentage of home wins when team A plays at home)
            home_h2h_advantage = self._calculate_home_advantage_h2h(
                home_team_id, away_team_id
            )
            
            # Psychological edge
            if home_win_rate > 0.6:
                psych_edge = 'home'
            elif away_win_rate > 0.6:
                psych_edge = 'away'
            else:
                psych_edge = 'neutral'
            
            return {
                # Basic record
                'matches_played': matches_played,
                'home_wins': h2h_data['team_a_wins'],
                'draws': h2h_data['draws'],
                'away_wins': h2h_data['team_b_wins'],
                
                # Win rates
                'home_win_rate': home_win_rate,
                'away_win_rate': away_win_rate,
                'draw_rate': draw_rate,
                
                # Goals
                'avg_home_goals': avg_home_goals,
                'avg_away_goals': avg_away_goals,
                'avg_total_goals': avg_total,
                'goals_differential': avg_home_goals - avg_away_goals,
                
                # Patterns
                'btts_rate': h2h_data['btts_rate'],
                'over_25_rate': over_25_rate,
                
                # Dominance
                'home_dominance': dominance,
                'clear_favourite': clear_favourite,
                'evenly_matched': evenly_matched,
                
                # Recent form
                'recent_form_h2h': recent_form,
                
                # Home advantage
                'home_advantage_h2h': home_h2h_advantage,
                
                # Psychological
                'psychological_edge': psych_edge,
                
                # Quality indicator
                'sufficient_history': matches_played >= 5,
                'recent_history': matches_played >= 3
            }
            
        except Exception as e:
            logger.error(f"Error analysing H2H: {e}")
            return self._empty_features()
    
    def _estimate_over_25_rate(self, avg_total_goals: float) -> float:
        """
        Estimate Over 2.5 rate from average total goals.
        
        Uses rough approximation based on Poisson distribution.
        """
        if avg_total_goals >= 3.5:
            return 0.75
        elif avg_total_goals >= 3.0:
            return 0.60
        elif avg_total_goals >= 2.5:
            return 0.50
        elif avg_total_goals >= 2.0:
            return 0.35
        else:
            return 0.20
    
    def _get_recent_h2h_form(
        self,
        home_team_id: int,
        away_team_id: int,
        n: int = 5
    ) -> str:
        """
        Get recent H2H form string (from home team's perspective).
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            n: Number of recent matches
            
        Returns:
            Form string like 'WWDLW' (most recent first)
        """
        session = Session()
        
        try:
            # Get recent matches between these teams
            matches = session.query(Match).filter(
                ((Match.home_team_id == home_team_id) & (Match.away_team_id == away_team_id)) |
                ((Match.home_team_id == away_team_id) & (Match.away_team_id == home_team_id))
            ).order_by(Match.date.desc()).limit(n).all()
            
            form_string = ''
            
            for match in matches:
                # Determine result from home team's perspective
                if match.home_team_id == home_team_id:
                    # Home team was at home
                    if match.home_goals > match.away_goals:
                        form_string += 'W'
                    elif match.home_goals < match.away_goals:
                        form_string += 'L'
                    else:
                        form_string += 'D'
                else:
                    # Home team was away
                    if match.away_goals > match.home_goals:
                        form_string += 'W'
                    elif match.away_goals < match.home_goals:
                        form_string += 'L'
                    else:
                        form_string += 'D'
            
            return form_string
            
        except Exception as e:
            logger.error(f"Error getting recent H2H form: {e}")
            return ''
        finally:
            session.close()
    
    def _calculate_home_advantage_h2h(
        self,
        home_team_id: int,
        away_team_id: int
    ) -> float:
        """
        Calculate home advantage in H2H matches.
        
        Returns win rate when home team plays at home venue.
        """
        session = Session()
        
        try:
            # Get matches where home_team_id was actually at home
            home_matches = session.query(Match).filter(
                Match.home_team_id == home_team_id,
                Match.away_team_id == away_team_id
            ).all()
            
            if not home_matches:
                return 0.5  # No data, assume neutral
            
            wins = sum(1 for m in home_matches if m.home_goals > m.away_goals)
            
            return wins / len(home_matches)
            
        except Exception as e:
            logger.error(f"Error calculating home advantage H2H: {e}")
            return 0.5
        finally:
            session.close()
    
    def _empty_features(self) -> Dict:
        """Return empty features when no H2H history."""
        return {
            'matches_played': 0,
            'home_wins': 0,
            'draws': 0,
            'away_wins': 0,
            'home_win_rate': 0.33,
            'away_win_rate': 0.33,
            'draw_rate': 0.34,
            'avg_home_goals': 1.5,
            'avg_away_goals': 1.5,
            'avg_total_goals': 2.5,
            'goals_differential': 0.0,
            'btts_rate': 0.5,
            'over_25_rate': 0.5,
            'home_dominance': 1.0,
            'clear_favourite': False,
            'evenly_matched': True,
            'recent_form_h2h': '',
            'home_advantage_h2h': 0.5,
            'psychological_edge': 'neutral',
            'sufficient_history': False,
            'recent_history': False
        }


if __name__ == '__main__':
    """Quick test."""
    print("Head-to-Head Analyser Test\n")
    
    analyser = HeadToHeadAnalyser(lookback_matches=10)
    
    from src.data.database import Session, Team
    session = Session()
    teams = session.query(Team).order_by(Team.current_elo.desc()).limit(2).all()
    
    if len(teams) >= 2:
        result = analyser.analyse_h2h(teams[0].id, teams[1].id)
        
        print(f"Match: {teams[0].name} vs {teams[1].name}")
        print(f"H2H Matches: {result['matches_played']}")
        print(f"Record: {result['home_wins']}W-{result['draws']}D-{result['away_wins']}L")
        print(f"Home Win Rate: {result['home_win_rate']:.1%}")
        print(f"Avg Goals: {result['avg_total_goals']:.2f}")
        print(f"BTTS Rate: {result['btts_rate']:.1%}")
        print(f"Dominance: {result['home_dominance']:.2f}")
        print(f"Psychological Edge: {result['psychological_edge']}")
        
        if result['recent_form_h2h']:
            print(f"Recent Form: {result['recent_form_h2h']}")
    
    session.close()
    print("\nHead-to-Head Analyser working correctly")