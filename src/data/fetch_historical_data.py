"""
Data Validator - Dataset-level validation and quality monitoring.

This complements src/utils/validators.py (field-level validation)
with dataset-level checks:
- Data completeness (missing matches, gaps in fixtures)
- Data consistency (ELO ratings make sense, odds are reasonable)
- Data quality metrics (what % of data is complete?)
- Data freshness (is data up-to-date?)

Professional betting requires confidence in data quality.
This module provides that confidence through comprehensive validation.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from src.data.database import Match, Team, Odds, Referee
from src.utils.logger import setup_logging
from src.utils.validators import validate_odds, validate_score, ValidationError

logger = setup_logging()


class DataQualityReport:
    """
    Data quality report with metrics and issues.
    """
    
    def __init__(self):
        self.metrics = {}
        self.issues = []
        self.warnings = []
        self.timestamp = datetime.now()
    
    def add_metric(self, name: str, value: Any) -> None:
        """Add a quality metric."""
        self.metrics[name] = value
    
    def add_issue(self, severity: str, description: str, details: Optional[Dict] = None) -> None:
        """
        Add a data quality issue.
        
        Args:
            severity: 'critical', 'error', 'warning', or 'info'
            description: Human-readable description
            details: Optional dictionary with additional details
        """
        issue = {
            'severity': severity,
            'description': description,
            'details': details or {},
            'timestamp': datetime.now()
        }
        
        if severity in ['critical', 'error']:
            self.issues.append(issue)
        else:
            self.warnings.append(issue)
    
    def is_healthy(self) -> bool:
        """Check if data quality is acceptable."""
        # No critical issues
        critical_issues = [i for i in self.issues if i['severity'] == 'critical']
        return len(critical_issues) == 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'metrics': self.metrics,
            'issues_count': len(self.issues),
            'warnings_count': len(self.warnings),
            'is_healthy': self.is_healthy(),
            'issues': self.issues,
            'warnings': self.warnings
        }
    
    def __str__(self) -> str:
        """String representation."""
        return f"DataQualityReport(metrics={len(self.metrics)}, issues={len(self.issues)}, warnings={len(self.warnings)})"


class DataValidator:
    """
    Comprehensive data quality validation.
    
    Usage:
        validator = DataValidator(session)
        
        # Run full validation
        report = validator.validate_all()
        
        # Check specific aspects
        validator.check_data_completeness()
        validator.check_data_consistency()
        validator.check_data_freshness()
    """
    
    def __init__(self, session: Session):
        """
        Initialise data validator.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.report = DataQualityReport()
        
        logger.info("Data validator initialised")
    
    def validate_all(self, days_back: int = 30) -> DataQualityReport:
        """
        Run all validation checks.
        
        Args:
            days_back: Validate data from last N days
            
        Returns:
            DataQualityReport with findings
        """
        logger.info(f"Running full data validation (last {days_back} days)")
        
        # Reset report
        self.report = DataQualityReport()
        
        # Run all checks
        self.check_data_completeness(days_back)
        self.check_data_consistency()
        self.check_data_freshness()
        self.check_odds_quality()
        self.check_for_missing_fixtures()
        self.calculate_quality_metrics()
        
        # Log summary
        summary = self.report.get_summary()
        logger.info(f"✓ Validation complete")
        logger.info(f"  - Metrics: {len(summary['metrics'])}")
        logger.info(f"  - Issues: {summary['issues_count']}")
        logger.info(f"  - Warnings: {summary['warnings_count']}")
        logger.info(f"  - Health: {'✓ HEALTHY' if summary['is_healthy'] else '✗ UNHEALTHY'}")
        
        return self.report
    
    def check_data_completeness(self, days_back: int = 30) -> None:
        """
        Check for missing or incomplete data.
        
        Args:
            days_back: Check matches from last N days
        """
        logger.info("Checking data completeness")
        
        start_date = datetime.now() - timedelta(days=days_back)
        
        # Get all finished matches
        finished_matches = self.session.query(Match).filter(
            Match.status == 'FINISHED',
            Match.date >= start_date
        ).all()
        
        total_matches = len(finished_matches)
        
        if total_matches == 0:
            self.report.add_issue(
                'warning',
                f'No finished matches in last {days_back} days',
                {'days_back': days_back}
            )
            return
        
        # Check for missing scores
        missing_scores = sum(1 for m in finished_matches 
                           if m.home_goals is None or m.away_goals is None)
        
        # Check for missing corners
        missing_corners = sum(1 for m in finished_matches 
                            if m.home_corners is None or m.away_corners is None)
        
        # Check for missing cards
        missing_cards = sum(1 for m in finished_matches 
                          if m.home_cards is None or m.away_cards is None)
        
        # Check for missing referee
        missing_referee = sum(1 for m in finished_matches if m.referee_id is None)
        
        # Calculate percentages
        score_completeness = ((total_matches - missing_scores) / total_matches) * 100
        corners_completeness = ((total_matches - missing_corners) / total_matches) * 100
        cards_completeness = ((total_matches - missing_cards) / total_matches) * 100
        referee_completeness = ((total_matches - missing_referee) / total_matches) * 100
        
        # Add metrics
        self.report.add_metric('total_finished_matches', total_matches)
        self.report.add_metric('score_completeness', f'{score_completeness:.1f}%')
        self.report.add_metric('corners_completeness', f'{corners_completeness:.1f}%')
        self.report.add_metric('cards_completeness', f'{cards_completeness:.1f}%')
        self.report.add_metric('referee_completeness', f'{referee_completeness:.1f}%')
        
        # Add issues if completeness is low
        if score_completeness < 95:
            self.report.add_issue(
                'critical',
                f'Low score completeness: {score_completeness:.1f}%',
                {'missing_count': missing_scores, 'total': total_matches}
            )
        
        if corners_completeness < 70:
            self.report.add_issue(
                'warning',
                f'Low corners completeness: {corners_completeness:.1f}%',
                {'missing_count': missing_corners}
            )
        
        if cards_completeness < 70:
            self.report.add_issue(
                'warning',
                f'Low cards completeness: {cards_completeness:.1f}%',
                {'missing_count': missing_cards}
            )
        
        logger.info(f"  - Score completeness: {score_completeness:.1f}%")
        logger.info(f"  - Corners completeness: {corners_completeness:.1f}%")
        logger.info(f"  - Cards completeness: {cards_completeness:.1f}%")
    
    def check_data_consistency(self) -> None:
        """
        Check for logical inconsistencies in data.
        """
        logger.info("Checking data consistency")
        
        # Check for impossible scores
        impossible_scores = self.session.query(Match).filter(
            or_(
                Match.home_goals < 0,
                Match.away_goals < 0,
                Match.home_corners < 0,
                Match.away_corners < 0,
                Match.home_cards < 0,
                Match.away_cards < 0
            )
        ).all()
        
        if impossible_scores:
            self.report.add_issue(
                'error',
                f'Found {len(impossible_scores)} matches with negative values',
                {'match_ids': [m.id for m in impossible_scores]}
            )
        
        # Check for matches with same teams
        same_team_matches = self.session.query(Match).filter(
            Match.home_team_id == Match.away_team_id
        ).all()
        
        if same_team_matches:
            self.report.add_issue(
                'critical',
                f'Found {len(same_team_matches)} matches where home == away team',
                {'match_ids': [m.id for m in same_team_matches]}
            )
        
        # Check ELO ratings are reasonable (between 1000 and 2500)
        unreasonable_elo = self.session.query(Team).filter(
            or_(
                Team.current_elo < 1000,
                Team.current_elo > 2500
            )
        ).all()
        
        if unreasonable_elo:
            self.report.add_issue(
                'warning',
                f'Found {len(unreasonable_elo)} teams with unusual ELO ratings',
                {'team_ids': [t.id for t in unreasonable_elo]}
            )
        
        # Check for duplicate matches
        # (same teams, same date within 1 hour)
        duplicates = self._find_duplicate_matches()
        if duplicates:
            self.report.add_issue(
                'error',
                f'Found {len(duplicates)} potential duplicate matches',
                {'duplicate_pairs': duplicates[:10]}  # Show first 10
            )
    
    def _find_duplicate_matches(self) -> List[Tuple[int, int]]:
        """
        Find potential duplicate matches.
        
        Returns:
            List of (match_id1, match_id2) tuples
        """
        duplicates = []
        
        all_matches = self.session.query(Match).order_by(Match.date).all()
        
        for i, match1 in enumerate(all_matches):
            for match2 in all_matches[i+1:i+50]:  # Only check next 50 matches
                if (match1.home_team_id == match2.home_team_id and
                    match1.away_team_id == match2.away_team_id and
                    match1.league_id == match2.league_id):
                    
                    time_diff = abs((match1.date - match2.date).total_seconds())
                    if time_diff < 3600:  # Within 1 hour
                        duplicates.append((match1.id, match2.id))
        
        return duplicates
    
    def check_data_freshness(self) -> None:
        """
        Check if data is up-to-date.
        """
        logger.info("Checking data freshness")
        
        # Get most recent match
        most_recent_match = self.session.query(Match).order_by(
            Match.date.desc()
        ).first()
        
        if not most_recent_match:
            self.report.add_issue(
                'critical',
                'No matches in database',
                {}
            )
            return
        
        # Check how old the most recent match is
        days_old = (datetime.now() - most_recent_match.date).days
        
        self.report.add_metric('most_recent_match_date', most_recent_match.date.isoformat())
        self.report.add_metric('most_recent_match_age_days', days_old)
        
        if days_old > 7:
            self.report.add_issue(
                'warning',
                f'Most recent match is {days_old} days old - data may be stale',
                {'last_match_date': most_recent_match.date.isoformat()}
            )
        
        # Check for today's fixtures
        today = datetime.now().date()
        today_fixtures = self.session.query(Match).filter(
            func.date(Match.date) == today
        ).count()
        
        self.report.add_metric('fixtures_today', today_fixtures)
        
        if today_fixtures == 0:
            # Only warn if it's a typical match day (Friday-Sunday)
            if today.weekday() in [4, 5, 6]:  # Fri, Sat, Sun
                self.report.add_issue(
                    'info',
                    f'No fixtures scheduled for today ({today})',
                    {}
                )
    
    def check_odds_quality(self) -> None:
        """
        Check quality of odds data.
        """
        logger.info("Checking odds quality")
        
        # Get recent odds
        recent_odds = self.session.query(Odds).filter(
            Odds.timestamp >= datetime.now() - timedelta(days=7)
        ).all()
        
        if len(recent_odds) == 0:
            self.report.add_issue(
                'critical',
                'No odds data in last 7 days',
                {}
            )
            return
        
        self.report.add_metric('total_odds_records', len(recent_odds))
        
        # Check for invalid odds values
        invalid_odds = []
        for odds in recent_odds:
            try:
                validate_odds(odds.odds)
            except ValidationError:
                invalid_odds.append(odds.id)
        
        if invalid_odds:
            self.report.add_issue(
                'error',
                f'Found {len(invalid_odds)} invalid odds values',
                {'odds_ids': invalid_odds[:20]}  # Show first 20
            )
        
        # Check bookmaker coverage
        bookmakers = defaultdict(int)
        for odds in recent_odds:
            bookmakers[odds.bookmaker] += 1
        
        self.report.add_metric('unique_bookmakers', len(bookmakers))
        self.report.add_metric('bookmaker_coverage', dict(bookmakers))
        
        if len(bookmakers) < 3:
            self.report.add_issue(
                'warning',
                f'Only {len(bookmakers)} bookmakers represented',
                {'bookmakers': list(bookmakers.keys())}
            )
        
        # Check market coverage
        markets = defaultdict(int)
        for odds in recent_odds:
            markets[odds.market] += 1
        
        self.report.add_metric('market_coverage', dict(markets))
        
        # Check for odds staleness
        stale_threshold = datetime.now() - timedelta(hours=24)
        stale_odds = sum(1 for o in recent_odds if o.timestamp < stale_threshold)
        
        staleness_pct = (stale_odds / len(recent_odds)) * 100
        self.report.add_metric('stale_odds_percentage', f'{staleness_pct:.1f}%')
        
        if staleness_pct > 50:
            self.report.add_issue(
                'warning',
                f'{staleness_pct:.1f}% of odds are >24h old',
                {}
            )
    
    def check_for_missing_fixtures(self, days_ahead: int = 7) -> None:
        """
        Check if we have upcoming fixtures scheduled.
        
        Args:
            days_ahead: Check fixtures for next N days
        """
        logger.info(f"Checking for upcoming fixtures (next {days_ahead} days)")
        
        end_date = datetime.now() + timedelta(days=days_ahead)
        
        upcoming_fixtures = self.session.query(Match).filter(
            Match.date >= datetime.now(),
            Match.date <= end_date,
            Match.status == 'SCHEDULED'
        ).all()
        
        self.report.add_metric('upcoming_fixtures_count', len(upcoming_fixtures))
        
        if len(upcoming_fixtures) == 0:
            self.report.add_issue(
                'warning',
                f'No fixtures scheduled for next {days_ahead} days',
                {'days_ahead': days_ahead}
            )
        
        # Check fixture distribution by league
        by_league = defaultdict(int)
        for match in upcoming_fixtures:
            by_league[match.league_id] += 1
        
        self.report.add_metric('fixtures_by_league', dict(by_league))
    
    def calculate_quality_metrics(self) -> None:
        """
        Calculate overall data quality metrics.
        """
        logger.info("Calculating quality metrics")
        
        # Overall completeness score (0-100)
        # Based on: scores, corners, cards data availability
        
        total_finished = self.session.query(Match).filter(
            Match.status == 'FINISHED'
        ).count()
        
        if total_finished == 0:
            self.report.add_metric('overall_quality_score', 0)
            return
        
        scores_complete = self.session.query(Match).filter(
            Match.status == 'FINISHED',
            Match.home_goals.isnot(None),
            Match.away_goals.isnot(None)
        ).count()
        
        corners_complete = self.session.query(Match).filter(
            Match.status == 'FINISHED',
            Match.home_corners.isnot(None),
            Match.away_corners.isnot(None)
        ).count()
        
        cards_complete = self.session.query(Match).filter(
            Match.status == 'FINISHED',
            Match.home_cards.isnot(None),
            Match.away_cards.isnot(None)
        ).count()
        
        # Weighted average (scores are most important)
        quality_score = (
            (scores_complete / total_finished) * 0.5 +
            (corners_complete / total_finished) * 0.25 +
            (cards_complete / total_finished) * 0.25
        ) * 100
        
        self.report.add_metric('overall_quality_score', f'{quality_score:.1f}/100')
        
        # Grade the quality
        if quality_score >= 90:
            grade = 'A (Excellent)'
        elif quality_score >= 80:
            grade = 'B (Good)'
        elif quality_score >= 70:
            grade = 'C (Acceptable)'
        elif quality_score >= 60:
            grade = 'D (Poor)'
        else:
            grade = 'F (Unacceptable)'
        
        self.report.add_metric('data_quality_grade', grade)
        
        if quality_score < 80:
            self.report.add_issue(
                'warning' if quality_score >= 70 else 'error',
                f'Low overall data quality: {quality_score:.1f}/100',
                {'grade': grade}
            )
    
    def get_report(self) -> DataQualityReport:
        """Get the current data quality report."""
        return self.report


# Convenience functions

def validate_data_quality(session: Session, days_back: int = 30) -> DataQualityReport:
    """
    Quick function to validate data quality.
    
    Args:
        session: Database session
        days_back: Validate data from last N days
        
    Returns:
        DataQualityReport
    """
    validator = DataValidator(session)
    return validator.validate_all(days_back=days_back)


def print_quality_report(report: DataQualityReport) -> None:
    """
    Pretty-print a data quality report.
    
    Args:
        report: DataQualityReport to print
    """
    print("\n" + "=" * 70)
    print("📊 DATA QUALITY REPORT")
    print("=" * 70)
    
    # Print metrics
    print("\n📈 METRICS:")
    for name, value in report.metrics.items():
        print(f"  • {name}: {value}")
    
    # Print issues
    if report.issues:
        print(f"\n❌ ISSUES ({len(report.issues)}):")
        for issue in report.issues:
            print(f"  • [{issue['severity'].upper()}] {issue['description']}")
    
    # Print warnings
    if report.warnings:
        print(f"\n⚠️  WARNINGS ({len(report.warnings)}):")
        for warning in report.warnings:
            print(f"  • {warning['description']}")
    
    # Overall health
    print("\n" + "=" * 70)
    if report.is_healthy():
        print("✅ DATA QUALITY: HEALTHY")
    else:
        print("❌ DATA QUALITY: UNHEALTHY - ACTION REQUIRED")
    print("=" * 70 + "\n")


# Example usage and testing
if __name__ == "__main__":
    """Test data validator."""
    
    from src.data.database import Session, init_db
    
    logger.info("Testing Data Validator")
    logger.info("=" * 60)
    
    # Initialise database
    init_db()
    
    # Create session
    session = Session()
    
    try:
        # Run validation
        report = validate_data_quality(session, days_back=30)
        
        # Print report
        print_quality_report(report)
        
        logger.info("✓ Validation test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        session.close()