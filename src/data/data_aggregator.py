"""
Data Aggregator - Transform API responses into database models.

This module handles the ETL (Extract, Transform, Load) process:
- Extract: API responses (from Football-Data, Odds API)
- Transform: Convert to database model format
- Load: Insert/update database records

Key responsibilities:
- Parse API responses
- Handle missing/optional fields
- Detect and resolve duplicates
- Batch insert for efficiency
- Transaction management
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.data.database import (
    Match, Team, Odds, Referee,
    get_or_create_team, get_or_create_referee
)
from src.utils.logger import setup_logging
from src.utils.helpers import parse_iso_date, standardise_team_name
from src.utils.validators import validate_match_data, validate_odds

logger = setup_logging()


class DataAggregator:
    """
    Aggregates data from multiple API sources into the database.
    
    Usage:
        aggregator = DataAggregator(session)
        
        # Process Football-Data API matches
        matches = aggregator.aggregate_matches(api_matches)
        
        # Process Odds API odds
        odds_count = aggregator.aggregate_odds(api_odds)
    """
    
    def __init__(self, session: Session):
        """
        Initialise data aggregator.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.stats = {
            'matches_added': 0,
            'matches_updated': 0,
            'teams_added': 0,
            'odds_added': 0,
            'referees_added': 0,
            'errors': 0
        }
        
        logger.info("Data aggregator initialised")
    
    def aggregate_matches(
        self,
        api_matches: List[Dict[str, Any]],
        league_id: str,
        source: str = 'football-data'
    ) -> List[Match]:
        """
        Transform API match data into database Match objects.
        
        Args:
            api_matches: List of match dictionaries from API
            league_id: League identifier (e.g., 'PL', 'BL1')
            source: API source name
            
        Returns:
            List of created/updated Match objects
        """
        logger.info(f"Aggregating {len(api_matches)} matches from {source}")
        
        matches_created = []
        
        for api_match in api_matches:
            try:
                match = self._process_single_match(api_match, league_id, source)
                if match:
                    matches_created.append(match)
                    
            except Exception as e:
                logger.error(f"Failed to process match {api_match.get('id')}: {e}")
                self.stats['errors'] += 1
                continue
        
        # Commit all changes
        try:
            self.session.commit()
            logger.info(f"✓ Successfully aggregated {len(matches_created)} matches")
            logger.info(f"  - New: {self.stats['matches_added']}")
            logger.info(f"  - Updated: {self.stats['matches_updated']}")
            logger.info(f"  - Errors: {self.stats['errors']}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to commit matches: {e}")
            raise
        
        return matches_created
    
    def _process_single_match(
        self,
        api_match: Dict[str, Any],
        league_id: str,
        source: str
    ) -> Optional[Match]:
        """
        Process a single match from API response.
        
        Args:
            api_match: Match dictionary from API
            league_id: League identifier
            source: API source name
            
        Returns:
            Match object or None if processing failed
        """
        # Extract match details based on source
        if source == 'football-data':
            match_data = self._parse_football_data_match(api_match, league_id)
        else:
            logger.warning(f"Unknown source: {source}")
            return None
        
        # Validate match data
        try:
            validate_match_data(match_data)
        except Exception as e:
            logger.warning(f"Invalid match data: {e}")
            return None
        
        # Get or create teams
        home_team = get_or_create_team(
            self.session,
            name=match_data['home_team_name'],
            league_id=league_id,
            external_id=match_data.get('home_team_id')
        )
        
        away_team = get_or_create_team(
            self.session,
            name=match_data['away_team_name'],
            league_id=league_id,
            external_id=match_data.get('away_team_id')
        )
        
        # Get or create referee if available
        referee = None
        if match_data.get('referee_name'):
            referee = get_or_create_referee(
                self.session,
                name=match_data['referee_name']
            )
        
        # Check if match already exists
        existing_match = self.session.query(Match).filter_by(
            external_id=match_data['external_id']
        ).first()
        
        if existing_match:
            # Update existing match
            self._update_match(existing_match, match_data, home_team, away_team, referee)
            self.stats['matches_updated'] += 1
            return existing_match
        else:
            # Create new match
            new_match = self._create_match(match_data, home_team, away_team, referee, league_id)
            self.stats['matches_added'] += 1
            return new_match
    
    def _parse_football_data_match(
        self,
        api_match: Dict[str, Any],
        league_id: str
    ) -> Dict[str, Any]:
        """
        Parse Football-Data.org API match response.
        
        Args:
            api_match: Raw API match dictionary
            league_id: League identifier
            
        Returns:
            Standardised match data dictionary
        """
        # Parse date
        date_str = api_match.get('utcDate', '')
        match_date = parse_iso_date(date_str) if date_str else datetime.now()
        
        # Extract team information
        home_team = api_match.get('homeTeam', {})
        away_team = api_match.get('awayTeam', {})
        
        # Extract score if match is finished
        score = api_match.get('score', {})
        full_time = score.get('fullTime', {})
        
        home_goals = full_time.get('home')
        away_goals = full_time.get('away')
        
        # Extract referee
        referees = api_match.get('referees', [])
        referee_name = None
        for ref in referees:
            if ref.get('type') == 'REFEREE':
                referee_name = ref.get('name')
                break
        
        # Note: Football-Data API doesn't provide corners/cards data
        # You'll need to get this from another source or scraping
        
        return {
            'external_id': str(api_match.get('id')),
            'date': match_date,
            'home_team_name': home_team.get('name', ''),
            'home_team_id': home_team.get('id'),
            'away_team_name': away_team.get('name', ''),
            'away_team_id': away_team.get('id'),
            'league_id': league_id,
            'status': api_match.get('status', 'SCHEDULED'),
            'home_goals': home_goals,
            'away_goals': away_goals,
            'home_corners': None,  # Not available from this API
            'away_corners': None,
            'home_cards': None,
            'away_cards': None,
            'referee_name': referee_name
        }
    
    def _create_match(
        self,
        match_data: Dict[str, Any],
        home_team: Team,
        away_team: Team,
        referee: Optional[Referee],
        league_id: str
    ) -> Match:
        """
        Create a new Match object.
        
        Args:
            match_data: Match information dictionary
            home_team: Home Team object
            away_team: Away Team object
            referee: Optional Referee object
            league_id: League identifier
            
        Returns:
            Created Match object
        """
        match = Match(
            external_id=match_data['external_id'],
            date=match_data['date'],
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            league_id=league_id,
            status=match_data['status'],
            home_goals=match_data.get('home_goals'),
            away_goals=match_data.get('away_goals'),
            home_corners=match_data.get('home_corners'),
            away_corners=match_data.get('away_corners'),
            home_cards=match_data.get('home_cards'),
            away_cards=match_data.get('away_cards'),
            referee_id=referee.id if referee else None
        )
        
        self.session.add(match)
        logger.debug(f"Created match: {home_team.name} vs {away_team.name}")
        
        return match
    
    def _update_match(
        self,
        match: Match,
        match_data: Dict[str, Any],
        home_team: Team,
        away_team: Team,
        referee: Optional[Referee]
    ) -> None:
        """
        Update an existing Match object.
        
        Only updates fields that may change (status, score, etc.)
        
        Args:
            match: Existing Match object
            match_data: Updated match information
            home_team: Home Team object
            away_team: Away Team object
            referee: Optional Referee object
        """
        # Update mutable fields
        match.status = match_data['status']
        match.home_goals = match_data.get('home_goals')
        match.away_goals = match_data.get('away_goals')
        match.home_corners = match_data.get('home_corners')
        match.away_corners = match_data.get('away_corners')
        match.home_cards = match_data.get('home_cards')
        match.away_cards = match_data.get('away_cards')
        match.referee_id = referee.id if referee else match.referee_id
        match.updated_at = datetime.utcnow()
        
        logger.debug(f"Updated match: {home_team.name} vs {away_team.name}")
    
    def aggregate_odds(
        self,
        api_odds: List[Dict[str, Any]],
        match_mapping: Optional[Dict[str, int]] = None
    ) -> int:
        """
        Transform API odds data into database Odds objects.
        
        Args:
            api_odds: List of odds dictionaries from Odds API
            match_mapping: Optional mapping of external match IDs to database match IDs
            
        Returns:
            Number of odds records created
        """
        logger.info(f"Aggregating odds for {len(api_odds)} events")
        
        odds_count = 0
        
        for event in api_odds:
            try:
                count = self._process_event_odds(event, match_mapping)
                odds_count += count
                
            except Exception as e:
                logger.error(f"Failed to process odds for event {event.get('id')}: {e}")
                self.stats['errors'] += 1
                continue
        
        # Commit all odds
        try:
            self.session.commit()
            logger.info(f"✓ Successfully aggregated {odds_count} odds records")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to commit odds: {e}")
            raise
        
        self.stats['odds_added'] = odds_count
        return odds_count
    
    def _process_event_odds(
        self,
        event: Dict[str, Any],
        match_mapping: Optional[Dict[str, int]]
    ) -> int:
        """
        Process odds for a single event.
        
        Args:
            event: Event dictionary from Odds API
            match_mapping: Optional match ID mapping
            
        Returns:
            Number of odds records created
        """
        # Find corresponding match in database
        home_team_name = event.get('home_team', '')
        away_team_name = event.get('away_team', '')
        
        # Try to find match by team names
        match = self._find_match_by_teams(home_team_name, away_team_name)
        
        if not match:
            logger.warning(f"Could not find match: {home_team_name} vs {away_team_name}")
            return 0
        
        odds_count = 0
        
        # Process each bookmaker's odds
        for bookmaker in event.get('bookmakers', []):
            bookmaker_name = bookmaker.get('title', bookmaker.get('key', 'unknown'))
            
            # Process each market
            for market in bookmaker.get('markets', []):
                market_key = market.get('key')
                
                # Process each outcome
                for outcome in market.get('outcomes', []):
                    try:
                        odds_value = outcome.get('price')
                        selection = outcome.get('name')
                        
                        # Validate odds
                        validate_odds(odds_value)
                        
                        # Create odds record
                        odds = Odds(
                            match_id=match.id,
                            bookmaker=bookmaker_name,
                            market=market_key,
                            selection=selection,
                            odds=odds_value,
                            timestamp=datetime.utcnow()
                        )
                        
                        self.session.add(odds)
                        odds_count += 1
                        
                    except Exception as e:
                        logger.debug(f"Failed to add odds: {e}")
                        continue
        
        return odds_count
    
    def _find_match_by_teams(
        self,
        home_team_name: str,
        away_team_name: str,
        date_window_days: int = 7
    ) -> Optional[Match]:
        """
        Find a match by team names.
        
        Uses fuzzy matching on standardised team names.
        
        Args:
            home_team_name: Home team name
            away_team_name: Away team name
            date_window_days: Look for matches within this many days
            
        Returns:
            Match object or None if not found
        """
        # Standardise team names
        home_std = standardise_team_name(home_team_name)
        away_std = standardise_team_name(away_team_name)
        
        # Find teams
        home_team = self.session.query(Team).filter(
            Team.name.ilike(f"%{home_std}%")
        ).first()
        
        away_team = self.session.query(Team).filter(
            Team.name.ilike(f"%{away_std}%")
        ).first()
        
        if not home_team or not away_team:
            return None
        
        # Find match within date window
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=date_window_days)
        end_date = datetime.now() + timedelta(days=date_window_days)
        
        match = self.session.query(Match).filter(
            Match.home_team_id == home_team.id,
            Match.away_team_id == away_team.id,
            Match.date >= start_date,
            Match.date <= end_date
        ).first()
        
        return match
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get aggregation statistics.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self.stats:
            self.stats[key] = 0


# Convenience functions for quick data aggregation

def aggregate_football_data_matches(
    session: Session,
    api_matches: List[Dict[str, Any]],
    league_id: str
) -> List[Match]:
    """
    Quick function to aggregate Football-Data API matches.
    
    Args:
        session: Database session
        api_matches: List of match dictionaries from API
        league_id: League identifier
        
    Returns:
        List of Match objects
    """
    aggregator = DataAggregator(session)
    return aggregator.aggregate_matches(api_matches, league_id, source='football-data')


def aggregate_odds(
    session: Session,
    api_odds: List[Dict[str, Any]]
) -> int:
    """
    Quick function to aggregate Odds API data.
    
    Args:
        session: Database session
        api_odds: List of odds dictionaries from API
        
    Returns:
        Number of odds records created
    """
    aggregator = DataAggregator(session)
    return aggregator.aggregate_odds(api_odds)


# Example usage and testing
if __name__ == "__main__":
    """Test data aggregator with sample data."""
    
    from src.data.database import Session, init_db
    
    logger.info("Testing Data Aggregator")
    logger.info("=" * 60)
    
    # Initialise database
    init_db()
    
    # Create session
    session = Session()
    
    try:
        # Sample Football-Data API match
        sample_match = {
            'id': 12345,
            'utcDate': '2024-01-15T15:00:00Z',
            'status': 'SCHEDULED',
            'homeTeam': {'id': 65, 'name': 'Manchester City'},
            'awayTeam': {'id': 57, 'name': 'Arsenal'},
            'score': {'fullTime': {'home': None, 'away': None}},
            'referees': [{'name': 'M. Oliver', 'type': 'REFEREE'}]
        }
        
        # Test match aggregation
        aggregator = DataAggregator(session)
        matches = aggregator.aggregate_matches([sample_match], 'PL', 'football-data')
        
        logger.info(f"✓ Created {len(matches)} matches")
        logger.info(f"Stats: {aggregator.get_stats()}")
        
        # Clean up test data
        for match in matches:
            session.delete(match)
        session.commit()
        
        logger.info("✓ Data aggregator test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        session.rollback()
    finally:
        session.close()