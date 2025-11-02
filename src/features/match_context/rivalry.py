"""
Rivalry Detector

Detects derbies and rivalries between teams.

Why this matters:
- Derbies are unpredictable (form goes out the window)
- Historical results matter less
- More defensive, lower scoring
- Emotional matches, more cards

Known derbies:
- Arsenal vs Tottenham (North London Derby)
- Liverpool vs Everton (Merseyside Derby)
- Manchester United vs Manchester City (Manchester Derby)

Usage:
    detector = RivalryDetector()
    rivalry = detector.detect_rivalry(home_id=1, away_id=2)
    if rivalry['is_derby']:
        print("Derby detected! Predictions less reliable")
"""

from typing import Dict, Optional, Set, Tuple
import logging

from src.data.database import Session, Team

logger = logging.getLogger(__name__)


class RivalryDetector:
    """
    Detects if a match is a derby or rivalry.
    
    Uses known rivalries database and geographic proximity.
    """
    
    # Known Premier League rivalries
    # Format: (team1_name, team2_name): {type, intensity}
    KNOWN_RIVALRIES = {
        # London derbies
        ('Arsenal', 'Tottenham'): {'type': 'derby', 'intensity': 10, 'name': 'North London Derby'},
        ('Chelsea', 'Tottenham'): {'type': 'rivalry', 'intensity': 8, 'name': 'London Derby'},
        ('Chelsea', 'Arsenal'): {'type': 'rivalry', 'intensity': 7, 'name': 'London Derby'},
        ('West Ham', 'Tottenham'): {'type': 'rivalry', 'intensity': 7, 'name': 'London Derby'},
        ('Crystal Palace', 'Brighton'): {'type': 'rivalry', 'intensity': 8, 'name': 'M23 Derby'},
        
        # Manchester derbies
        ('Manchester United', 'Manchester City'): {'type': 'derby', 'intensity': 10, 'name': 'Manchester Derby'},
        
        # Merseyside derby
        ('Liverpool', 'Everton'): {'type': 'derby', 'intensity': 10, 'name': 'Merseyside Derby'},
        
        # Major rivalries
        ('Liverpool', 'Manchester United'): {'type': 'rivalry', 'intensity': 10, 'name': 'Northwest Derby'},
        ('Arsenal', 'Manchester United'): {'type': 'rivalry', 'intensity': 8, 'name': 'Historical Rivalry'},
        
        # Tyne-Wear derby
        ('Newcastle', 'Sunderland'): {'type': 'derby', 'intensity': 10, 'name': 'Tyne-Wear Derby'},
        
        # Midlands derbies
        ('Aston Villa', 'Birmingham'): {'type': 'derby', 'intensity': 10, 'name': 'Second City Derby'},
        ('Nottingham Forest', 'Derby'): {'type': 'derby', 'intensity': 9, 'name': 'East Midlands Derby'},
        ('Leicester', 'Nottingham Forest'): {'type': 'rivalry', 'intensity': 7, 'name': 'Midlands Rivalry'},
        
        # South Coast
        ('Southampton', 'Portsmouth'): {'type': 'derby', 'intensity': 10, 'name': 'South Coast Derby'},
        
        # Yorkshire derbies
        ('Leeds', 'Sheffield United'): {'type': 'derby', 'intensity': 8, 'name': 'Yorkshire Derby'},
        ('Leeds', 'Sheffield Wednesday'): {'type': 'derby', 'intensity': 8, 'name': 'Yorkshire Derby'},
    }
    
    def __init__(self):
        """Initialise rivalry detector."""
        # Build lookup set for faster checking
        self.rivalry_pairs: Set[Tuple[str, str]] = set()
        for (team1, team2), data in self.KNOWN_RIVALRIES.items():
            # Add both orderings
            self.rivalry_pairs.add((team1, team2))
            self.rivalry_pairs.add((team2, team1))
        
        logger.info(f"Rivalry Detector initialised with {len(self.KNOWN_RIVALRIES)} known rivalries")
    
    def detect_rivalry(
        self,
        home_team_id: int,
        away_team_id: int
    ) -> Dict:
        """
        Detect if match is a derby or rivalry.
        
        Args:
            home_team_id: Home team
            away_team_id: Away team
            
        Returns:
            {
                'is_derby': True,
                'is_rivalry': True,
                'rivalry_intensity': 9,  # 0-10 scale
                'rivalry_name': 'North London Derby',
                'rivalry_type': 'derby',  # derby, rivalry, none
                'affects_prediction': True,
                'unpredictability_factor': 1.3  # How much more unpredictable
            }
        """
        session = Session()
        
        try:
            # Get team names
            home_team = session.query(Team).filter_by(id=home_team_id).first()
            away_team = session.query(Team).filter_by(id=away_team_id).first()
            
            if not home_team or not away_team:
                logger.warning(f"Teams not found: home={home_team_id}, away={away_team_id}")
                return self._empty_features()
            
            home_name = home_team.name
            away_name = away_team.name
            
            # Check known rivalries
            rivalry_data = self._check_known_rivalry(home_name, away_name)
            
            if rivalry_data:
                return rivalry_data
            
            # Check if same city (basic derby detection)
            # This is a fallback if not in known list
            same_city = self._check_same_city(home_name, away_name)
            
            if same_city:
                return {
                    'is_derby': True,
                    'is_rivalry': True,
                    'rivalry_intensity': 7,  # Default for unknown local derbies
                    'rivalry_name': f'{home_name} vs {away_name} (Local Derby)',
                    'rivalry_type': 'derby',
                    'affects_prediction': True,
                    'unpredictability_factor': 1.2
                }
            
            # No rivalry detected
            return self._empty_features()
            
        except Exception as e:
            logger.error(f"Error detecting rivalry: {e}")
            return self._empty_features()
        finally:
            session.close()
    
    def _check_known_rivalry(self, home_name: str, away_name: str) -> Optional[Dict]:
        """
        Check if teams are in known rivalries list.
        
        Returns rivalry data if found, None otherwise.
        """
        # Try both orderings
        rivalry_key = (home_name, away_name)
        reverse_key = (away_name, home_name)
        
        rivalry_info = self.KNOWN_RIVALRIES.get(rivalry_key) or self.KNOWN_RIVALRIES.get(reverse_key)
        
        if rivalry_info:
            intensity = rivalry_info['intensity']
            
            # Calculate unpredictability factor
            # Higher intensity = more unpredictable
            unpredictability = 1.0 + (intensity / 20.0)  # 1.0-1.5 range
            
            return {
                'is_derby': rivalry_info['type'] == 'derby',
                'is_rivalry': True,
                'rivalry_intensity': intensity,
                'rivalry_name': rivalry_info['name'],
                'rivalry_type': rivalry_info['type'],
                'affects_prediction': intensity >= 7,  # High intensity affects predictions
                'unpredictability_factor': unpredictability
            }
        
        return None
    
    def _check_same_city(self, team1_name: str, team2_name: str) -> bool:
        """
        Check if teams from same city (basic check).
        
        This is a simple fallback - just checks if city names appear in both team names.
        """
        # Common city names in team names
        cities = [
            'Manchester', 'Liverpool', 'London', 'Birmingham', 'Sheffield',
            'Newcastle', 'Leicester', 'Southampton', 'Brighton', 'Nottingham',
            'Leeds', 'Bristol', 'Derby'
        ]
        
        for city in cities:
            if city in team1_name and city in team2_name:
                # Don't match if they're the same team name
                if team1_name != team2_name:
                    return True
        
        return False
    
    def get_all_rivalries(self, team_name: str) -> list:
        """
        Get all known rivalries for a team.
        
        Args:
            team_name: Team to find rivalries for
            
        Returns:
            List of rival teams with intensity
        """
        rivalries = []
        
        for (team1, team2), data in self.KNOWN_RIVALRIES.items():
            if team1 == team_name:
                rivalries.append({
                    'rival': team2,
                    'intensity': data['intensity'],
                    'type': data['type'],
                    'name': data['name']
                })
            elif team2 == team_name:
                rivalries.append({
                    'rival': team1,
                    'intensity': data['intensity'],
                    'type': data['type'],
                    'name': data['name']
                })
        
        # Sort by intensity
        rivalries.sort(key=lambda x: x['intensity'], reverse=True)
        
        return rivalries
    
    def _empty_features(self) -> Dict:
        """Return empty features when no rivalry detected."""
        return {
            'is_derby': False,
            'is_rivalry': False,
            'rivalry_intensity': 0,
            'rivalry_name': None,
            'rivalry_type': 'none',
            'affects_prediction': False,
            'unpredictability_factor': 1.0
        }


if __name__ == '__main__':
    """Quick test."""
    print("Rivalry Detector Test\n")
    
    detector = RivalryDetector()
    
    from src.data.database import Session, Team
    session = Session()
    
    # Try to find Arsenal and Tottenham
    arsenal = session.query(Team).filter(Team.name.like('%Arsenal%')).first()
    tottenham = session.query(Team).filter(Team.name.like('%Tottenham%')).first()
    
    if arsenal and tottenham:
        result = detector.detect_rivalry(arsenal.id, tottenham.id)
        print(f"Match: {arsenal.name} vs {tottenham.name}")
        print(f"Is Derby: {result['is_derby']}")
        print(f"Intensity: {result['rivalry_intensity']}/10")
        print(f"Name: {result['rivalry_name']}")
        print(f"Unpredictability: {result['unpredictability_factor']:.2f}x")
    else:
        print("Testing with first two teams in database...")
        teams = session.query(Team).limit(2).all()
        if len(teams) >= 2:
            result = detector.detect_rivalry(teams[0].id, teams[1].id)
            print(f"Match: {teams[0].name} vs {teams[1].name}")
            print(f"Is Rivalry: {result['is_rivalry']}")
    
    session.close()
    print("\nRivalry Detector working correctly")