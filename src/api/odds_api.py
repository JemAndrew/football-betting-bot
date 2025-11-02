"""
The Odds API client for fetching betting odds.

API Documentation: https://the-odds-api.com/liveapi/guides/v4/

Free Tier Limits:
- 500 requests per month (~17 per day)
- Be VERY careful with quota!

Provides:
- Live odds from multiple bookmakers
- Multiple betting markets (h2h, totals, spreads)
- Historical odds (premium feature)

IMPORTANT: This API has very limited free quota.
Use caching aggressively and be selective about requests.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import os

from src.api.base_api import BaseAPI
from src.utils.logger import setup_logging

logger = setup_logging()


class OddsAPI(BaseAPI):
    """
    Client for The Odds API.
    
    QUOTA MANAGEMENT:
    - Free tier: 500 requests/month
    - Each request to /odds endpoint counts as 1-2 requests (varies by bookmakers)
    - Use cache_ttl_hours=24 to minimise requests
    - Only fetch odds when actually needed for betting decisions
    
    Usage:
        api = OddsAPI()
        
        # Get odds for Premier League
        odds = api.get_odds('soccer_epl_premier_league')
        
        # Get specific markets
        odds = api.get_odds('soccer_epl_premier_league', markets='h2h,totals')
        
        # Check quota remaining
        quota = api.check_quota()
    """
    
    # Sport keys mapping
    SPORTS = {
        'soccer_epl': 'English Premier League',
        'soccer_spain_la_liga': 'La Liga',
        'soccer_germany_bundesliga': 'Bundesliga',
        'soccer_italy_serie_a': 'Serie A',
        'soccer_france_ligue_one': 'Ligue 1',
        'soccer_uefa_champs_league': 'Champions League',
        'soccer_uefa_europa_league': 'Europa League'
    }
    
    # Available betting markets
    MARKETS = {
        'h2h': 'Head to Head (1X2)',
        'spreads': 'Handicap',
        'totals': 'Over/Under Goals',
        'btts': 'Both Teams To Score',
        'outrights': 'Tournament Winner'
    }
    
    # Available regions (determines which bookmakers)
    REGIONS = {
        'uk': 'United Kingdom bookmakers',
        'eu': 'European bookmakers',
        'us': 'United States bookmakers',
        'au': 'Australian bookmakers'
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise Odds API client.
        
        Args:
            api_key: API key (defaults to ODDS_API_KEY env var)
        """
        if api_key is None:
            api_key = os.getenv('ODDS_API_KEY')
            if not api_key:
                raise ValueError("ODDS_API_KEY not found in environment variables")
        
        super().__init__(
            base_url="https://api.the-odds-api.com/v4",
            api_key=api_key,
            rate_limit=30,  # Conservative rate limit
            enable_cache=True,
            cache_ttl_hours=24  # Cache for 24 hours to save quota
        )
        
        self.requests_used = 0
        self.requests_remaining = 500  # Default assumption
        
        logger.info("Odds API client initialised")
        logger.warning("Free tier has only 500 requests/month - use sparingly!")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get headers for The Odds API.
        Uses apiKey query parameter, not header.
        """
        return {
            "Content-Type": "application/json"
        }
    
    def _make_request(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Override to track quota usage from response headers.
        """
        response_data = super()._make_request(*args, **kwargs)
        
        # The Odds API returns quota info in headers
        # We'll need to access the raw response to get this
        # For now, just increment our counter
        self.requests_used += 1
        self.requests_remaining = max(0, 500 - self.requests_used)
        
        if self.requests_remaining < 50:
            logger.warning(f"⚠️  Low quota: only {self.requests_remaining} requests remaining!")
        
        return response_data
    
    def get_sports(self, all_sports: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of available sports.
        
        Args:
            all_sports: If True, return all sports (including out-of-season).
                       If False, return only in-season sports.
        
        Returns:
            List of sport dictionaries
            
        Example response:
            [{
                'key': 'soccer_epl',
                'group': 'Soccer',
                'title': 'English Premier League',
                'description': 'EPL',
                'active': True,
                'has_outrights': False
            }]
        """
        params = {'apiKey': self.api_key}
        if all_sports:
            params['all'] = 'true'
        
        logger.info(f"Fetching available sports (all={all_sports})")
        sports = self.get("/sports", params=params)
        
        logger.info(f"Found {len(sports)} sports")
        return sports
    
    def get_odds(
        self,
        sport_key: str,
        regions: str = 'uk',
        markets: str = 'h2h',
        odds_format: str = 'decimal',
        date_format: str = 'iso',
        bookmakers: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get odds for a specific sport.
        
        ⚠️  WARNING: Each call uses 1-2 API requests depending on parameters.
        Use caching and call sparingly!
        
        Args:
            sport_key: Sport identifier (e.g., 'soccer_epl')
            regions: Comma-separated regions (e.g., 'uk,eu')
            markets: Comma-separated markets (e.g., 'h2h,totals,btts')
            odds_format: 'decimal' or 'american'
            date_format: 'iso' or 'unix'
            bookmakers: Optional comma-separated list of bookmaker names
            
        Returns:
            List of event dictionaries with odds
            
        Example response:
            [{
                'id': 'abc123',
                'sport_key': 'soccer_epl',
                'sport_title': 'EPL',
                'commence_time': '2024-01-15T15:00:00Z',
                'home_team': 'Manchester City',
                'away_team': 'Arsenal',
                'bookmakers': [
                    {
                        'key': 'bet365',
                        'title': 'Bet365',
                        'markets': [
                            {
                                'key': 'h2h',
                                'outcomes': [
                                    {'name': 'Manchester City', 'price': 1.80},
                                    {'name': 'Arsenal', 'price': 2.20},
                                    {'name': 'Draw', 'price': 3.40}
                                ]
                            }
                        ]
                    }
                ]
            }]
        """
        params = {
            'apiKey': self.api_key,
            'regions': regions,
            'markets': markets,
            'oddsFormat': odds_format,
            'dateFormat': date_format
        }
        
        if bookmakers:
            params['bookmakers'] = bookmakers
        
        logger.info(f"Fetching odds for {sport_key} (regions={regions}, markets={markets})")
        logger.warning(f"⏳ Using API quota - {self.requests_remaining} requests remaining")
        
        # Use cache aggressively to save quota
        odds_data = self.get(f"/sports/{sport_key}/odds", params=params, use_cache=True)
        
        logger.info(f"Found odds for {len(odds_data)} events")
        return odds_data
    
    def get_event_odds(
        self,
        sport_key: str,
        event_id: str,
        regions: str = 'uk',
        markets: str = 'h2h',
        odds_format: str = 'decimal',
        date_format: str = 'iso',
        bookmakers: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get odds for a specific event.
        
        Args:
            sport_key: Sport identifier
            event_id: Event ID from get_odds()
            regions: Regions to get odds from
            markets: Markets to include
            odds_format: 'decimal' or 'american'
            date_format: 'iso' or 'unix'
            bookmakers: Optional bookmaker filter
            
        Returns:
            Single event dictionary with odds
        """
        params = {
            'apiKey': self.api_key,
            'regions': regions,
            'markets': markets,
            'oddsFormat': odds_format,
            'dateFormat': date_format
        }
        
        if bookmakers:
            params['bookmakers'] = bookmakers
        
        logger.info(f"Fetching odds for event {event_id}")
        event_data = self.get(
            f"/sports/{sport_key}/odds/{event_id}",
            params=params,
            use_cache=True
        )
        
        return event_data
    
    def get_historical_odds(
        self,
        sport_key: str,
        event_id: str,
        regions: str = 'uk',
        markets: str = 'h2h',
        odds_format: str = 'decimal',
        date_format: str = 'iso'
    ) -> List[Dict[str, Any]]:
        """
        Get historical odds for an event (Premium feature).
        
        ⚠️  Note: This requires a premium API plan.
        
        Args:
            sport_key: Sport identifier
            event_id: Event ID
            regions: Regions filter
            markets: Markets filter
            odds_format: 'decimal' or 'american'
            date_format: 'iso' or 'unix'
            
        Returns:
            List of historical odds snapshots
        """
        params = {
            'apiKey': self.api_key,
            'regions': regions,
            'markets': markets,
            'oddsFormat': odds_format,
            'dateFormat': date_format
        }
        
        logger.info(f"Fetching historical odds for event {event_id}")
        logger.info("Note: This requires a premium API plan")
        
        historical_data = self.get(
            f"/sports/{sport_key}/odds-history/{event_id}",
            params=params,
            use_cache=True
        )
        
        return historical_data
    
    def check_quota(self) -> Dict[str, Any]:
        """
        Check remaining API quota.
        
        Returns:
            Dictionary with quota information
        """
        # Make a minimal request to check headers
        try:
            sports = self.get_sports()
            
            quota_info = {
                'requests_used': self.requests_used,
                'requests_remaining': self.requests_remaining,
                'total_quota': 500,
                'percentage_used': (self.requests_used / 500) * 100
            }
            
            logger.info(f"Quota status: {self.requests_used}/500 used "
                       f"({quota_info['percentage_used']:.1f}%)")
            
            return quota_info
            
        except Exception as e:
            logger.error(f"Failed to check quota: {e}")
            return {
                'requests_used': self.requests_used,
                'requests_remaining': 'unknown',
                'error': str(e)
            }
    
    def get_best_odds(
        self,
        sport_key: str,
        market: str = 'h2h',
        regions: str = 'uk'
    ) -> List[Dict[str, Any]]:
        """
        Get best available odds across all bookmakers.
        
        Args:
            sport_key: Sport identifier
            market: Market to analyse (e.g., 'h2h', 'totals')
            regions: Regions to search
            
        Returns:
            List of events with best odds highlighted
        """
        odds_data = self.get_odds(
            sport_key=sport_key,
            regions=regions,
            markets=market,
            odds_format='decimal'
        )
        
        results = []
        
        for event in odds_data:
            event_result = {
                'home_team': event['home_team'],
                'away_team': event['away_team'],
                'commence_time': event['commence_time'],
                'best_odds': {}
            }
            
            # Find best odds for each outcome
            for bookmaker in event.get('bookmakers', []):
                for market_data in bookmaker.get('markets', []):
                    if market_data['key'] == market:
                        for outcome in market_data.get('outcomes', []):
                            outcome_name = outcome['name']
                            odds = outcome['price']
                            
                            if outcome_name not in event_result['best_odds']:
                                event_result['best_odds'][outcome_name] = {
                                    'odds': odds,
                                    'bookmaker': bookmaker['title']
                                }
                            elif odds > event_result['best_odds'][outcome_name]['odds']:
                                event_result['best_odds'][outcome_name] = {
                                    'odds': odds,
                                    'bookmaker': bookmaker['title']
                                }
            
            results.append(event_result)
        
        return results


# Example usage and testing
if __name__ == "__main__":
    """
    Test Odds API client.
    Requires ODDS_API_KEY in environment variables.
    
    ⚠️  WARNING: Running these tests will use API quota!
    Comment out tests if you want to preserve quota.
    """
    try:
        logger.info("=" * 60)
        logger.info("Testing Odds API Client")
        logger.info("=" * 60)
        
        # Initialise API client
        api = OddsAPI()
        logger.info("✓ API client initialised")
        
        # Test 1: Check quota first
        logger.info("\nTest 1: Checking API quota...")
        quota = api.check_quota()
        logger.info(f"✓ Quota remaining: {quota['requests_remaining']}")
        
        if quota.get('requests_remaining', 0) < 10:
            logger.warning("⚠️  Low quota - skipping remaining tests")
        else:
            # Test 2: Get available sports
            logger.info("\nTest 2: Fetching available sports...")
            sports = api.get_sports()
            logger.info(f"✓ Found {len(sports)} sports")
            
            soccer_sports = [s for s in sports if s['group'] == 'Soccer']
            for sport in soccer_sports[:3]:
                logger.info(f"  - {sport['title']} ({sport['key']})")
            
            # Test 3: Get odds for Premier League
            logger.info("\nTest 3: Fetching Premier League odds...")
            logger.warning("⚠️  This will use API quota!")
            
            odds = api.get_odds(
                sport_key='soccer_epl',
                regions='uk',
                markets='h2h,totals',
                odds_format='decimal'
            )
            
            logger.info(f"✓ Found odds for {len(odds)} events")
            
            if odds:
                first_match = odds[0]
                logger.info(f"\n  Match: {first_match['home_team']} vs {first_match['away_team']}")
                logger.info(f"  Kick-off: {first_match['commence_time']}")
                logger.info(f"  Bookmakers: {len(first_match.get('bookmakers', []))}")
                
                # Show first bookmaker's odds
                if first_match.get('bookmakers'):
                    bookmaker = first_match['bookmakers'][0]
                    logger.info(f"\n  {bookmaker['title']} odds:")
                    for market in bookmaker.get('markets', []):
                        logger.info(f"    {market['key']}:")
                        for outcome in market.get('outcomes', []):
                            logger.info(f"      {outcome['name']}: {outcome['price']}")
        
        # Final quota check
        logger.info("\nFinal quota check...")
        final_quota = api.check_quota()
        logger.info(f"Requests used in this session: {api.requests_used}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ Tests complete!")
        logger.info("=" * 60)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Make sure ODDS_API_KEY is set in .env file")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())