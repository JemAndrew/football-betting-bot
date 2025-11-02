"""
Football-Data.org API client for fetching match data.

API Documentation: https://www.football-data.org/documentation/quickstart

Free Tier Limits:
- 10 requests per minute
- Limited to certain competitions

Provides:
- Match fixtures (upcoming and past)
- Match results
- League standings
- Team information
- Competition details
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import os

from src.api.base_api import BaseAPI
from src.utils.logger import setup_logging
from src.utils.helpers import parse_iso_date, format_date

logger = setup_logging()


class FootballDataAPI(BaseAPI):
    """
    Client for Football-Data.org API.
    
    Usage:
        api = FootballDataAPI()
        
        # Get Premier League fixtures
        fixtures = api.get_fixtures('PL')
        
        # Get recent matches
        matches = api.get_matches('PL', date_from='2024-01-01', date_to='2024-01-31')
        
        # Get league table
        standings = api.get_standings('PL')
    """
    
    # Competition codes mapping
    COMPETITIONS = {
        'PL': 'Premier League',
        'PD': 'La Liga',
        'BL1': 'Bundesliga',
        'SA': 'Serie A',
        'FL1': 'Ligue 1',
        'CL': 'Champions League',
        'EL': 'Europa League'
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise Football-Data API client.
        
        Args:
            api_key: API key (defaults to FOOTBALL_DATA_API_KEY env var)
        """
        if api_key is None:
            api_key = os.getenv('FOOTBALL_DATA_API_KEY')
            if not api_key:
                raise ValueError("FOOTBALL_DATA_API_KEY not found in environment variables")
        
        super().__init__(
            base_url="https://api.football-data.org/v4",
            api_key=api_key,
            rate_limit=10,  # 10 requests per minute for free tier
            enable_cache=True,
            cache_ttl_hours=6  # Cache for 6 hours (fixtures change frequently)
        )
        
        logger.info("Football-Data API client initialised")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get headers for Football-Data API.
        Uses X-Auth-Token header for authentication.
        """
        return {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json"
        }
    
    def get_competitions(self) -> List[Dict[str, Any]]:
        """
        Get list of available competitions.
        
        Returns:
            List of competition dictionaries with details
            
        Example response structure:
            [{
                'id': 2021,
                'name': 'Premier League',
                'code': 'PL',
                'type': 'LEAGUE',
                'emblem': 'https://...',
                'currentSeason': {...}
            }]
        """
        logger.info("Fetching available competitions")
        response = self.get("/competitions")
        
        competitions = response.get('competitions', [])
        logger.info(f"Found {len(competitions)} competitions")
        
        return competitions
    
    def get_competition(self, competition_code: str) -> Dict[str, Any]:
        """
        Get details for a specific competition.
        
        Args:
            competition_code: Competition code (e.g., 'PL', 'BL1')
            
        Returns:
            Competition details dictionary
        """
        logger.info(f"Fetching competition details for {competition_code}")
        response = self.get(f"/competitions/{competition_code}")
        
        return response
    
    def get_matches(
        self,
        competition_code: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        matchday: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get matches for a competition with optional filters.
        
        Args:
            competition_code: Competition code (e.g., 'PL')
            date_from: Start date (YYYY-MM-DD format)
            date_to: End date (YYYY-MM-DD format)
            status: Match status ('SCHEDULED', 'LIVE', 'IN_PLAY', 'PAUSED', 'FINISHED')
            matchday: Specific matchday number
            
        Returns:
            List of match dictionaries
            
        Example response structure:
            [{
                'id': 12345,
                'utcDate': '2024-01-15T15:00:00Z',
                'status': 'FINISHED',
                'matchday': 21,
                'homeTeam': {'id': 65, 'name': 'Manchester City'},
                'awayTeam': {'id': 57, 'name': 'Arsenal'},
                'score': {
                    'fullTime': {'home': 2, 'away': 1},
                    'halfTime': {'home': 1, 'away': 0}
                },
                'referees': [{'name': 'M. Oliver', 'type': 'REFEREE'}]
            }]
        """
        params = {}
        
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
        if status:
            params['status'] = status
        if matchday:
            params['matchday'] = matchday
        
        logger.info(f"Fetching matches for {competition_code} with filters: {params}")
        response = self.get(f"/competitions/{competition_code}/matches", params=params)
        
        matches = response.get('matches', [])
        logger.info(f"Found {len(matches)} matches")
        
        return matches
    
    def get_fixtures(
        self,
        competition_code: str,
        days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming fixtures for a competition.
        
        Args:
            competition_code: Competition code (e.g., 'PL')
            days_ahead: Number of days to look ahead (default: 7)
            
        Returns:
            List of upcoming match dictionaries
        """
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)
        
        date_from = format_date(today)
        date_to = format_date(end_date)
        
        logger.info(f"Fetching fixtures for {competition_code} "
                   f"from {date_from} to {date_to}")
        
        return self.get_matches(
            competition_code=competition_code,
            date_from=date_from,
            date_to=date_to,
            status='SCHEDULED'
        )
    
    def get_results(
        self,
        competition_code: str,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get recent results for a competition.
        
        Args:
            competition_code: Competition code (e.g., 'PL')
            days_back: Number of days to look back (default: 7)
            
        Returns:
            List of finished match dictionaries
        """
        today = datetime.now().date()
        start_date = today - timedelta(days=days_back)
        
        date_from = format_date(start_date)
        date_to = format_date(today)
        
        logger.info(f"Fetching results for {competition_code} "
                   f"from {date_from} to {date_to}")
        
        return self.get_matches(
            competition_code=competition_code,
            date_from=date_from,
            date_to=date_to,
            status='FINISHED'
        )
    
    def get_match(self, match_id: int) -> Dict[str, Any]:
        """
        Get details for a specific match.
        
        Args:
            match_id: Match ID from Football-Data
            
        Returns:
            Match details dictionary with full information
        """
        logger.info(f"Fetching match details for ID {match_id}")
        response = self.get(f"/matches/{match_id}")
        
        return response
    
    def get_standings(self, competition_code: str) -> List[Dict[str, Any]]:
        """
        Get league standings for a competition.
        
        Args:
            competition_code: Competition code (e.g., 'PL')
            
        Returns:
            List of standings with team positions and stats
            
        Example response structure:
            [{
                'position': 1,
                'team': {'id': 65, 'name': 'Manchester City'},
                'playedGames': 20,
                'won': 15,
                'draw': 3,
                'lost': 2,
                'points': 48,
                'goalsFor': 45,
                'goalsAgainst': 18,
                'goalDifference': 27,
                'form': 'W,W,D,W,W'
            }]
        """
        logger.info(f"Fetching standings for {competition_code}")
        response = self.get(f"/competitions/{competition_code}/standings")
        
        standings = response.get('standings', [])
        if standings:
            # Usually returns multiple standings types (TOTAL, HOME, AWAY)
            # We want TOTAL standings
            for standing_type in standings:
                if standing_type.get('type') == 'TOTAL':
                    table = standing_type.get('table', [])
                    logger.info(f"Found {len(table)} teams in standings")
                    return table
        
        logger.warning(f"No TOTAL standings found for {competition_code}")
        return []
    
    def get_team(self, team_id: int) -> Dict[str, Any]:
        """
        Get details for a specific team.
        
        Args:
            team_id: Team ID from Football-Data
            
        Returns:
            Team details dictionary
            
        Example response structure:
            {
                'id': 65,
                'name': 'Manchester City',
                'shortName': 'Man City',
                'tla': 'MCI',
                'crest': 'https://...',
                'founded': 1880,
                'venue': 'Etihad Stadium',
                'squad': [...]
            }
        """
        logger.info(f"Fetching team details for ID {team_id}")
        response = self.get(f"/teams/{team_id}")
        
        return response
    
    def get_team_matches(
        self,
        team_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get matches for a specific team.
        
        Args:
            team_id: Team ID from Football-Data
            date_from: Start date (YYYY-MM-DD format)
            date_to: End date (YYYY-MM-DD format)
            status: Match status filter
            
        Returns:
            List of match dictionaries involving this team
        """
        params = {}
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
        if status:
            params['status'] = status
        
        logger.info(f"Fetching matches for team ID {team_id} with filters: {params}")
        response = self.get(f"/teams/{team_id}/matches", params=params)
        
        matches = response.get('matches', [])
        logger.info(f"Found {len(matches)} matches for team")
        
        return matches
    
    def get_head_to_head(self, match_id: int) -> Dict[str, Any]:
        """
        Get head-to-head statistics for teams in a match.
        
        Args:
            match_id: Match ID from Football-Data
            
        Returns:
            Head-to-head statistics dictionary
        """
        logger.info(f"Fetching head-to-head data for match ID {match_id}")
        
        # H2H data is included in the match endpoint
        match_data = self.get_match(match_id)
        
        h2h_data = match_data.get('head2head', {})
        return h2h_data
    
    def get_scorers(self, competition_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top scorers for a competition.
        
        Args:
            competition_code: Competition code (e.g., 'PL')
            limit: Maximum number of scorers to return
            
        Returns:
            List of top scorer dictionaries
        """
        logger.info(f"Fetching top {limit} scorers for {competition_code}")
        response = self.get(f"/competitions/{competition_code}/scorers", params={'limit': limit})
        
        scorers = response.get('scorers', [])
        logger.info(f"Found {len(scorers)} scorers")
        
        return scorers


# Example usage and testing
if __name__ == "__main__":
    """
    Test Football-Data API client.
    Requires FOOTBALL_DATA_API_KEY in environment variables.
    """
    try:
        logger.info("=" * 60)
        logger.info("Testing Football-Data API Client")
        logger.info("=" * 60)
        
        # Initialise API client
        api = FootballDataAPI()
        logger.info("✓ API client initialised")
        
        # Test 1: Get competitions
        logger.info("\nTest 1: Fetching available competitions...")
        competitions = api.get_competitions()
        logger.info(f"✓ Found {len(competitions)} competitions")
        for comp in competitions[:3]:
            logger.info(f"  - {comp['name']} ({comp['code']})")
        
        # Test 2: Get Premier League fixtures
        logger.info("\nTest 2: Fetching Premier League fixtures (next 7 days)...")
        fixtures = api.get_fixtures('PL', days_ahead=7)
        logger.info(f"✓ Found {len(fixtures)} upcoming fixtures")
        if fixtures:
            first_fixture = fixtures[0]
            logger.info(f"  Next match: {first_fixture['homeTeam']['name']} vs "
                       f"{first_fixture['awayTeam']['name']}")
        
        # Test 3: Get recent results
        logger.info("\nTest 3: Fetching Premier League results (last 7 days)...")
        results = api.get_results('PL', days_back=7)
        logger.info(f"✓ Found {len(results)} recent results")
        if results:
            first_result = results[0]
            score = first_result['score']['fullTime']
            logger.info(f"  Recent: {first_result['homeTeam']['name']} "
                       f"{score['home']}-{score['away']} "
                       f"{first_result['awayTeam']['name']}")
        
        # Test 4: Get league standings
        logger.info("\nTest 4: Fetching Premier League standings...")
        standings = api.get_standings('PL')
        logger.info(f"✓ Found {len(standings)} teams in standings")
        if standings:
            top_team = standings[0]
            logger.info(f"  Top team: {top_team['team']['name']} "
                       f"({top_team['points']} points)")
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests passed! Football-Data API is working.")
        logger.info("=" * 60)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Make sure FOOTBALL_DATA_API_KEY is set in .env file")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())