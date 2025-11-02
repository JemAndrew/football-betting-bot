#!/usr/bin/env python3
"""
Daily Data Update Script

Automatically update the database with:
1. Yesterday's match results
2. Today's fixtures  
3. Current odds for upcoming matches
4. ELO rating updates

This script should be run daily via cron job.

Usage:
    python scripts/update_data.py [options]

Arguments:
    --leagues: Comma-separated league IDs (default: from config)
    --skip-odds: Skip odds fetching
    --skip-elo: Skip ELO updates
    --days-results: Days back to fetch results (default: 2)
    --days-fixtures: Days ahead to fetch fixtures (default: 7)

Example cron entry (run at 8am daily):
    0 8 * * * cd /path/to/project && /path/to/venv/bin/python scripts/update_data.py

Example usage:
    python scripts/update_data.py --leagues PL,BL1,PD
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.football_data_api import FootballDataAPI
from src.api.odds_api import OddsAPI
from src.data.database import Session, init_db, Match
from src.data.data_aggregator import DataAggregator
from src.data.data_cleaner import DataCleaner
from src.utils.logger import setup_logging, log_api_call
from src.utils.config_loader import get_config

logger = setup_logging()
config = get_config()


class DailyDataUpdater:
    """
    Handles daily data updates.
    """
    
    def __init__(
        self,
        football_api: FootballDataAPI,
        odds_api: OddsAPI = None,
        session: Session = None
    ):
        """
        Initialise daily data updater.
        
        Args:
            football_api: Football-Data API client
            odds_api: Optional Odds API client
            session: Optional database session
        """
        self.football_api = football_api
        self.odds_api = odds_api
        self.session = session or Session()
        
        self.aggregator = DataAggregator(self.session)
        
        self.stats = {
            'results_updated': 0,
            'fixtures_added': 0,
            'odds_updated': 0,
            'elo_updates': 0,
            'api_calls': 0,
            'errors': 0
        }
        
        logger.info("Daily data updater initialised")
    
    def update_results(
        self,
        league_ids: List[str],
        days_back: int = 2
    ) -> int:
        """
        Update results for recent matches.
        
        Args:
            league_ids: List of league identifiers
            days_back: Number of days back to check
            
        Returns:
            Number of matches updated
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📥 UPDATING RESULTS (last {days_back} days)")
        logger.info(f"{'='*70}\n")
        
        total_updated = 0
        
        for league_id in league_ids:
            logger.info(f"Fetching {league_id} results...")
            
            try:
                # Fetch recent results
                results = self.football_api.get_results(
                    competition_code=league_id,
                    days_back=days_back
                )
                
                self.stats['api_calls'] += 1
                
                logger.info(f"  ✓ Found {len(results)} finished matches")
                
                # Store in database
                if results:
                    matches = self.aggregator.aggregate_matches(
                        results,
                        league_id=league_id,
                        source='football-data'
                    )
                    
                    total_updated += len(matches)
                
                # Respect rate limit
                time.sleep(6)
                
            except Exception as e:
                logger.error(f"  ✗ Failed to fetch results: {e}")
                self.stats['errors'] += 1
        
        self.stats['results_updated'] = total_updated
        
        logger.info(f"\n✓ Updated {total_updated} match results\n")
        
        return total_updated
    
    def update_fixtures(
        self,
        league_ids: List[str],
        days_ahead: int = 7
    ) -> int:
        """
        Update upcoming fixtures.
        
        Args:
            league_ids: List of league identifiers
            days_ahead: Number of days ahead to fetch
            
        Returns:
            Number of fixtures added/updated
        """
        logger.info(f"{'='*70}")
        logger.info(f"📅 UPDATING FIXTURES (next {days_ahead} days)")
        logger.info(f"{'='*70}\n")
        
        total_fixtures = 0
        
        for league_id in league_ids:
            logger.info(f"Fetching {league_id} fixtures...")
            
            try:
                # Fetch upcoming fixtures
                fixtures = self.football_api.get_fixtures(
                    competition_code=league_id,
                    days_ahead=days_ahead
                )
                
                self.stats['api_calls'] += 1
                
                logger.info(f"  ✓ Found {len(fixtures)} upcoming matches")
                
                # Store in database
                if fixtures:
                    matches = self.aggregator.aggregate_matches(
                        fixtures,
                        league_id=league_id,
                        source='football-data'
                    )
                    
                    total_fixtures += len(matches)
                
                # Respect rate limit
                time.sleep(6)
                
            except Exception as e:
                logger.error(f"  ✗ Failed to fetch fixtures: {e}")
                self.stats['errors'] += 1
        
        self.stats['fixtures_added'] = total_fixtures
        
        logger.info(f"\n✓ Updated {total_fixtures} fixtures\n")
        
        return total_fixtures
    
    def update_odds(
        self,
        league_ids: List[str]
    ) -> int:
        """
        Update odds for upcoming matches.
        
        Args:
            league_ids: List of league identifiers
            
        Returns:
            Number of odds records added
        """
        if not self.odds_api:
            logger.warning("Odds API not available - skipping odds update")
            return 0
        
        logger.info(f"{'='*70}")
        logger.info("💰 UPDATING ODDS")
        logger.info(f"{'='*70}\n")
        
        # Map league IDs to Odds API sport keys
        league_mapping = {
            'PL': 'soccer_epl',
            'PD': 'soccer_spain_la_liga',
            'BL1': 'soccer_germany_bundesliga',
            'SA': 'soccer_italy_serie_a',
            'FL1': 'soccer_france_ligue_one'
        }
        
        total_odds = 0
        
        for league_id in league_ids:
            sport_key = league_mapping.get(league_id)
            
            if not sport_key:
                logger.warning(f"No Odds API mapping for {league_id}")
                continue
            
            logger.info(f"Fetching {league_id} odds...")
            
            try:
                # Fetch odds
                odds_data = self.odds_api.get_odds(
                    sport_key=sport_key,
                    regions='uk',
                    markets='h2h,totals,btts',
                    odds_format='decimal'
                )
                
                self.stats['api_calls'] += 1
                
                logger.info(f"  ✓ Found odds for {len(odds_data)} events")
                
                # Store in database
                if odds_data:
                    count = self.aggregator.aggregate_odds(odds_data)
                    total_odds += count
                
                # Respect rate limit (be conservative)
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"  ✗ Failed to fetch odds: {e}")
                self.stats['errors'] += 1
        
        self.stats['odds_updated'] = total_odds
        
        logger.info(f"\n✓ Updated {total_odds} odds records\n")
        
        return total_odds
    
    def update_elo_ratings(self) -> int:
        """
        Update ELO ratings for all teams based on recent results.
        
        Returns:
            Number of teams updated
        
        Note: This is a placeholder. In Phase 3, you'll implement
        the actual ELO calculation logic.
        """
        logger.info(f"{'='*70}")
        logger.info("📊 UPDATING ELO RATINGS")
        logger.info(f"{'='*70}\n")
        
        # TODO: Implement in Phase 3
        # For now, just log that this needs to be done
        
        logger.info("⚠️  ELO update not yet implemented")
        logger.info("  → Will be added in Phase 3 (Simple Models)")
        logger.info("  → See: src/features/elo_calculator.py\n")
        
        return 0
    
    def clean_data(self) -> None:
        """
        Run data cleaning on recent data.
        """
        logger.info(f"{'='*70}")
        logger.info("🧹 CLEANING DATA")
        logger.info(f"{'='*70}\n")
        
        cleaner = DataCleaner(self.session)
        
        # Only clean last 7 days
        cleaner.clean_matches(days_back=7)
        cleaner.impute_missing_values()
        
        logger.info("✓ Data cleaning complete\n")
    
    def print_summary(self) -> None:
        """Print update summary."""
        logger.info("="*70)
        logger.info("📊 UPDATE SUMMARY")
        logger.info("="*70)
        logger.info(f"Results updated: {self.stats['results_updated']}")
        logger.info(f"Fixtures added: {self.stats['fixtures_added']}")
        logger.info(f"Odds updated: {self.stats['odds_updated']}")
        logger.info(f"API calls made: {self.stats['api_calls']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Daily data update for betting bot',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--leagues',
        type=str,
        help='Comma-separated league IDs (default: from config)'
    )
    
    parser.add_argument(
        '--skip-odds',
        action='store_true',
        help='Skip odds fetching'
    )
    
    parser.add_argument(
        '--skip-elo',
        action='store_true',
        help='Skip ELO updates'
    )
    
    parser.add_argument(
        '--days-results',
        type=int,
        default=2,
        help='Days back to fetch results (default: 2)'
    )
    
    parser.add_argument(
        '--days-fixtures',
        type=int,
        default=7,
        help='Days ahead to fetch fixtures (default: 7)'
    )
    
    args = parser.parse_args()
    
    # Get league IDs
    if args.leagues:
        league_ids = [l.strip() for l in args.leagues.split(',')]
    else:
        # Get from config
        league_ids = config.get_enabled_leagues()
        if not league_ids:
            league_ids = ['PL']  # Default to Premier League
    
    logger.info("="*70)
    logger.info("⚽ FOOTBALL BETTING BOT - DAILY UPDATE")
    logger.info("="*70)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Leagues: {', '.join(league_ids)}")
    logger.info("="*70 + "\n")
    
    # Ensure database exists
    init_db()
    
    # Create API clients
    try:
        logger.info("Connecting to Football-Data API...")
        football_api = FootballDataAPI()
        logger.info("✓ Connected\n")
    except Exception as e:
        logger.error(f"Failed to initialise Football-Data API: {e}")
        logger.error("Make sure FOOTBALL_DATA_API_KEY is set in .env file")
        sys.exit(1)
    
    odds_api = None
    if not args.skip_odds:
        try:
            logger.info("Connecting to Odds API...")
            odds_api = OddsAPI()
            logger.info("✓ Connected\n")
        except Exception as e:
            logger.warning(f"Could not initialise Odds API: {e}")
            logger.warning("Continuing without odds updates\n")
    
    # Create session
    session = Session()
    
    try:
        # Create updater
        updater = DailyDataUpdater(
            football_api=football_api,
            odds_api=odds_api,
            session=session
        )
        
        # Update results
        updater.update_results(
            league_ids=league_ids,
            days_back=args.days_results
        )
        
        # Update fixtures
        updater.update_fixtures(
            league_ids=league_ids,
            days_ahead=args.days_fixtures
        )
        
        # Update odds
        if not args.skip_odds:
            updater.update_odds(league_ids=league_ids)
        
        # Update ELO ratings
        if not args.skip_elo:
            updater.update_elo_ratings()
        
        # Clean data
        updater.clean_data()
        
        # Print summary
        updater.print_summary()
        
        # Success message
        logger.info("="*70)
        logger.info("✅ DAILY UPDATE COMPLETE!")
        logger.info("="*70)
        
        if updater.stats['errors'] > 0:
            logger.warning(f"\n⚠️  {updater.stats['errors']} errors occurred - check logs")
        
        logger.info("\n" + "="*70 + "\n")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        session.rollback()
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        session.rollback()
        sys.exit(1)
        
    finally:
        session.close()


if __name__ == "__main__":
    main()