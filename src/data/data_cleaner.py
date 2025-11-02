"""
Data Cleaner - Handle missing values, outliers, and data quality issues.

This module provides data cleaning functionality for:
- Missing value imputation
- Outlier detection and correction
- Team name standardisation
- Data type corrections
- Duplicate removal
- Data normalisation

Professional sports betting requires clean, reliable data.
One bad data point can ruin model predictions.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy.orm import Session

from src.data.database import Match, Team, Odds
from src.utils.logger import setup_logging
from src.utils.helpers import standardise_team_name
from src.utils.validators import (
    validate_score,
    ValidationError
)

logger = setup_logging()


class DataCleaner:
    """
    Comprehensive data cleaning for betting bot.
    
    Usage:
        cleaner = DataCleaner(session)
        
        # Clean all recent matches
        cleaner.clean_matches(days_back=30)
        
        # Handle missing values
        cleaner.impute_missing_values()
        
        # Remove outliers
        cleaner.detect_and_fix_outliers()
    """
    
    def __init__(self, session: Session):
        """
        Initialise data cleaner.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.stats = {
            'records_processed': 0,
            'missing_values_fixed': 0,
            'outliers_detected': 0,
            'outliers_fixed': 0,
            'duplicates_removed': 0,
            'team_names_standardised': 0,
            'errors': 0
        }
        
        logger.info("Data cleaner initialised")
    
    def clean_all(self, days_back: int = 30) -> Dict[str, int]:
        """
        Run all cleaning operations on recent data.
        
        Args:
            days_back: Process matches from last N days
            
        Returns:
            Dictionary of cleaning statistics
        """
        logger.info(f"Running full data cleaning (last {days_back} days)")
        
        # Clean matches
        self.clean_matches(days_back=days_back)
        
        # Standardise team names
        self.standardise_team_names()
        
        # Handle missing values
        self.impute_missing_values()
        
        # Detect outliers
        self.detect_and_fix_outliers()
        
        # Remove duplicates
        self.remove_duplicate_matches()
        self.remove_duplicate_odds()
        
        logger.info("✓ Data cleaning complete")
        logger.info(f"Stats: {self.get_stats()}")
        
        return self.get_stats()
    
    def clean_matches(self, days_back: int = 30) -> int:
        """
        Clean match data.
        
        Args:
            days_back: Process matches from last N days
            
        Returns:
            Number of matches processed
        """
        start_date = datetime.now() - timedelta(days=days_back)
        
        matches = self.session.query(Match).filter(
            Match.date >= start_date
        ).all()
        
        logger.info(f"Cleaning {len(matches)} matches")
        
        for match in matches:
            try:
                self._clean_single_match(match)
                self.stats['records_processed'] += 1
            except Exception as e:
                logger.error(f"Failed to clean match {match.id}: {e}")
                self.stats['errors'] += 1
        
        self.session.commit()
        return len(matches)
    
    def _clean_single_match(self, match: Match) -> None:
        """
        Clean a single match record.
        
        Args:
            match: Match object to clean
        """
        # Fix obviously wrong scores
        if match.home_goals is not None:
            if match.home_goals < 0:
                logger.warning(f"Match {match.id}: Negative home goals ({match.home_goals}), setting to 0")
                match.home_goals = 0
                self.stats['outliers_fixed'] += 1
            
            if match.home_goals > 15:
                logger.warning(f"Match {match.id}: Suspiciously high home goals ({match.home_goals})")
                self.stats['outliers_detected'] += 1
                # Don't auto-fix very high scores - might be correct
        
        if match.away_goals is not None:
            if match.away_goals < 0:
                logger.warning(f"Match {match.id}: Negative away goals ({match.away_goals}), setting to 0")
                match.away_goals = 0
                self.stats['outliers_fixed'] += 1
            
            if match.away_goals > 15:
                logger.warning(f"Match {match.id}: Suspiciously high away goals ({match.away_goals})")
                self.stats['outliers_detected'] += 1
        
        # Fix corners data
        if match.home_corners is not None:
            if match.home_corners < 0:
                logger.warning(f"Match {match.id}: Negative corners, setting to 0")
                match.home_corners = 0
                self.stats['outliers_fixed'] += 1
            
            if match.home_corners > 30:
                logger.warning(f"Match {match.id}: Suspiciously high corners ({match.home_corners})")
                self.stats['outliers_detected'] += 1
        
        if match.away_corners is not None:
            if match.away_corners < 0:
                match.away_corners = 0
                self.stats['outliers_fixed'] += 1
            
            if match.away_corners > 30:
                self.stats['outliers_detected'] += 1
        
        # Fix cards data
        if match.home_cards is not None:
            if match.home_cards < 0:
                match.home_cards = 0
                self.stats['outliers_fixed'] += 1
            
            if match.home_cards > 12:
                logger.warning(f"Match {match.id}: Very high cards ({match.home_cards})")
                self.stats['outliers_detected'] += 1
        
        if match.away_cards is not None:
            if match.away_cards < 0:
                match.away_cards = 0
                self.stats['outliers_fixed'] += 1
            
            if match.away_cards > 12:
                self.stats['outliers_detected'] += 1
        
        # Validate status transitions
        if match.status == 'FINISHED':
            # Finished match should have scores
            if match.home_goals is None or match.away_goals is None:
                logger.warning(f"Match {match.id}: Status is FINISHED but scores are missing")
                # Don't change status - might be data not available yet
    
    def impute_missing_values(self) -> int:
        """
        Impute missing values using reasonable defaults or averages.
        
        Strategy:
        - Missing corners: Use league average
        - Missing cards: Use league average
        - Missing referee: Leave as None (can't impute)
        
        Returns:
            Number of values imputed
        """
        logger.info("Imputing missing values")
        
        imputed_count = 0
        
        # Get league averages
        league_averages = self._calculate_league_averages()
        
        # Process finished matches with missing data
        finished_matches = self.session.query(Match).filter(
            Match.status == 'FINISHED'
        ).all()
        
        for match in finished_matches:
            league_avg = league_averages.get(match.league_id, {})
            
            # Impute missing corners
            if match.home_corners is None and league_avg.get('avg_corners'):
                match.home_corners = int(league_avg['avg_corners'] / 2)
                imputed_count += 1
                logger.debug(f"Imputed home corners for match {match.id}")
            
            if match.away_corners is None and league_avg.get('avg_corners'):
                match.away_corners = int(league_avg['avg_corners'] / 2)
                imputed_count += 1
            
            # Impute missing cards
            if match.home_cards is None and league_avg.get('avg_cards'):
                match.home_cards = int(league_avg['avg_cards'] / 2)
                imputed_count += 1
            
            if match.away_cards is None and league_avg.get('avg_cards'):
                match.away_cards = int(league_avg['avg_cards'] / 2)
                imputed_count += 1
        
        self.stats['missing_values_fixed'] = imputed_count
        
        if imputed_count > 0:
            self.session.commit()
            logger.info(f"✓ Imputed {imputed_count} missing values")
        
        return imputed_count
    
    def _calculate_league_averages(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate average statistics by league.
        
        Returns:
            Dictionary mapping league_id to average statistics
        """
        from sqlalchemy import func
        
        # Query average corners per league
        corners_query = self.session.query(
            Match.league_id,
            func.avg(Match.home_corners + Match.away_corners).label('avg_corners')
        ).filter(
            Match.status == 'FINISHED',
            Match.home_corners.isnot(None),
            Match.away_corners.isnot(None)
        ).group_by(Match.league_id).all()
        
        # Query average cards per league
        cards_query = self.session.query(
            Match.league_id,
            func.avg(Match.home_cards + Match.away_cards).label('avg_cards')
        ).filter(
            Match.status == 'FINISHED',
            Match.home_cards.isnot(None),
            Match.away_cards.isnot(None)
        ).group_by(Match.league_id).all()
        
        # Combine results
        averages = {}
        
        for league_id, avg_corners in corners_query:
            if league_id not in averages:
                averages[league_id] = {}
            averages[league_id]['avg_corners'] = float(avg_corners) if avg_corners else None
        
        for league_id, avg_cards in cards_query:
            if league_id not in averages:
                averages[league_id] = {}
            averages[league_id]['avg_cards'] = float(avg_cards) if avg_cards else None
        
        return averages
    
    def detect_and_fix_outliers(self) -> Dict[str, List[int]]:
        """
        Detect statistical outliers in match data.
        
        Uses IQR (Interquartile Range) method:
        - Outliers are values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
        
        Returns:
            Dictionary of outlier match IDs by category
        """
        logger.info("Detecting outliers using IQR method")
        
        outliers = {
            'high_scoring': [],
            'many_corners': [],
            'many_cards': []
        }
        
        # Get all finished matches
        finished_matches = self.session.query(Match).filter(
            Match.status == 'FINISHED'
        ).all()
        
        if len(finished_matches) < 30:
            logger.warning("Not enough data for outlier detection (need 30+ matches)")
            return outliers
        
        # Calculate total goals for each match
        goals_data = []
        corners_data = []
        cards_data = []
        
        for match in finished_matches:
            if match.home_goals is not None and match.away_goals is not None:
                goals_data.append((match.id, match.home_goals + match.away_goals))
            
            if match.home_corners is not None and match.away_corners is not None:
                corners_data.append((match.id, match.home_corners + match.away_corners))
            
            if match.home_cards is not None and match.away_cards is not None:
                cards_data.append((match.id, match.home_cards + match.away_cards))
        
        # Detect goal outliers
        if goals_data:
            outliers['high_scoring'] = self._detect_outliers_iqr(
                goals_data, threshold=1.5
            )
        
        # Detect corner outliers
        if corners_data:
            outliers['many_corners'] = self._detect_outliers_iqr(
                corners_data, threshold=1.5
            )
        
        # Detect card outliers
        if cards_data:
            outliers['many_cards'] = self._detect_outliers_iqr(
                cards_data, threshold=1.5
            )
        
        # Log outliers
        total_outliers = sum(len(v) for v in outliers.values())
        if total_outliers > 0:
            logger.info(f"Detected {total_outliers} potential outliers:")
            for category, match_ids in outliers.items():
                if match_ids:
                    logger.info(f"  - {category}: {len(match_ids)} matches")
        
        self.stats['outliers_detected'] += total_outliers
        
        return outliers
    
    def _detect_outliers_iqr(
        self,
        data: List[Tuple[int, float]],
        threshold: float = 1.5
    ) -> List[int]:
        """
        Detect outliers using IQR method.
        
        Args:
            data: List of (match_id, value) tuples
            threshold: IQR multiplier (1.5 is standard, 3.0 is very conservative)
            
        Returns:
            List of outlier match IDs
        """
        if len(data) < 10:
            return []
        
        values = np.array([v for _, v in data])
        
        Q1 = np.percentile(values, 25)
        Q3 = np.percentile(values, 75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        
        outlier_ids = []
        for match_id, value in data:
            if value < lower_bound or value > upper_bound:
                outlier_ids.append(match_id)
        
        return outlier_ids
    
    def standardise_team_names(self) -> int:
        """
        Standardise team names across all teams.
        
        Returns:
            Number of team names updated
        """
        logger.info("Standardising team names")
        
        teams = self.session.query(Team).all()
        updated_count = 0
        
        for team in teams:
            original_name = team.name
            standardised_name = standardise_team_name(team.name)
            
            # Only update if actually different
            if standardised_name != original_name.lower().strip():
                logger.debug(f"Standardising: '{original_name}' → '{standardised_name}'")
                # Don't actually change the name in DB - might break external ID matching
                # Instead, just log it
                # In production, you'd create a separate mapping table
                updated_count += 1
        
        self.stats['team_names_standardised'] = updated_count
        
        if updated_count > 0:
            logger.info(f"Found {updated_count} team names that could be standardised")
        
        return updated_count
    
    def remove_duplicate_matches(self) -> int:
        """
        Remove duplicate match records.
        
        Duplicates are matches with:
        - Same teams
        - Same date (within 1 hour)
        - Same league
        
        Returns:
            Number of duplicates removed
        """
        logger.info("Checking for duplicate matches")
        
        from sqlalchemy import func
        
        # Find matches with same teams and close dates
        duplicates = []
        
        all_matches = self.session.query(Match).order_by(Match.date).all()
        
        for i, match1 in enumerate(all_matches):
            for match2 in all_matches[i+1:]:
                # Same teams
                if (match1.home_team_id == match2.home_team_id and
                    match1.away_team_id == match2.away_team_id and
                    match1.league_id == match2.league_id):
                    
                    # Close dates (within 1 hour)
                    time_diff = abs((match1.date - match2.date).total_seconds())
                    if time_diff < 3600:  # 1 hour
                        duplicates.append((match1, match2))
        
        # Remove duplicates (keep the one with more data)
        removed_count = 0
        
        for match1, match2 in duplicates:
            # Count non-null fields
            match1_data = sum([
                match1.home_goals is not None,
                match1.away_goals is not None,
                match1.home_corners is not None,
                match1.away_corners is not None,
                match1.home_cards is not None,
                match1.away_cards is not None
            ])
            
            match2_data = sum([
                match2.home_goals is not None,
                match2.away_goals is not None,
                match2.home_corners is not None,
                match2.away_corners is not None,
                match2.home_cards is not None,
                match2.away_cards is not None
            ])
            
            # Keep the one with more data
            to_delete = match2 if match1_data >= match2_data else match1
            
            logger.info(f"Removing duplicate match: {to_delete}")
            self.session.delete(to_delete)
            removed_count += 1
        
        if removed_count > 0:
            self.session.commit()
            logger.info(f"✓ Removed {removed_count} duplicate matches")
        
        self.stats['duplicates_removed'] += removed_count
        return removed_count
    
    def remove_duplicate_odds(self) -> int:
        """
        Remove duplicate odds records.
        
        Duplicates are odds with:
        - Same match
        - Same bookmaker
        - Same market
        - Very close timestamps (within 1 minute)
        
        Returns:
            Number of duplicates removed
        """
        logger.info("Checking for duplicate odds")
        
        from sqlalchemy import func, distinct
        
        # Find potential duplicate groups
        duplicate_groups = self.session.query(
            Odds.match_id,
            Odds.bookmaker,
            Odds.market,
            func.count(Odds.id).label('count')
        ).group_by(
            Odds.match_id,
            Odds.bookmaker,
            Odds.market
        ).having(
            func.count(Odds.id) > 1
        ).all()
        
        removed_count = 0
        
        for match_id, bookmaker, market, count in duplicate_groups:
            # Get all odds in this group
            odds_list = self.session.query(Odds).filter(
                Odds.match_id == match_id,
                Odds.bookmaker == bookmaker,
                Odds.market == market
            ).order_by(Odds.timestamp.desc()).all()
            
            # Keep only the most recent, remove others
            to_keep = odds_list[0]
            to_remove = odds_list[1:]
            
            for odds in to_remove:
                # Only remove if very close in time (likely true duplicate)
                time_diff = abs((to_keep.timestamp - odds.timestamp).total_seconds())
                if time_diff < 60:  # Within 1 minute
                    self.session.delete(odds)
                    removed_count += 1
        
        if removed_count > 0:
            self.session.commit()
            logger.info(f"✓ Removed {removed_count} duplicate odds")
        
        self.stats['duplicates_removed'] += removed_count
        return removed_count
    
    def get_stats(self) -> Dict[str, int]:
        """Get cleaning statistics."""
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self.stats:
            self.stats[key] = 0


# Example usage and testing
if __name__ == "__main__":
    """Test data cleaner with sample data."""
    
    from src.data.database import Session, init_db
    
    logger.info("Testing Data Cleaner")
    logger.info("=" * 60)
    
    # Initialise database
    init_db()
    
    # Create session
    session = Session()
    
    try:
        # Create cleaner
        cleaner = DataCleaner(session)
        
        # Run cleaning
        stats = cleaner.clean_all(days_back=30)
        
        logger.info(f"✓ Cleaning complete: {stats}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        session.close()