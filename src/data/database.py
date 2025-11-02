"""
Database models and connection handling.

This module defines the SQLAlchemy ORM models for all database tables.
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from src.utils.config_loader import get_config
from src.utils.logger import setup_logging

# Set up logging
logger = setup_logging()

# Get database URL from config
config = get_config()
DATABASE_URL = config.get_database_url()

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    pool_pre_ping=True,  # Verify connections before using
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


# ============================================
# TABLE 1: TEAMS
# ============================================
class Team(Base):
    """Team model - stores team information and ELO ratings."""
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    league_id = Column(String(10), nullable=False)  # PL, PD, BL1, etc.
    external_id = Column(Integer, nullable=True)  # API team ID
    current_elo = Column(Float, default=1500.0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")
    
    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}', elo={self.current_elo:.0f})>"


# ============================================
# TABLE 2: REFEREES
# ============================================
class Referee(Base):
    """Referee model - stores referee statistics."""
    __tablename__ = "referees"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    avg_corners = Column(Float, nullable=True)
    avg_cards = Column(Float, nullable=True)
    matches_officiated = Column(Integer, default=0)
    
    # Relationships
    matches = relationship("Match", back_populates="referee")
    
    def __repr__(self):
        return f"<Referee(id={self.id}, name='{self.name}', matches={self.matches_officiated})>"


# ============================================
# TABLE 3: MATCHES
# ============================================
class Match(Base):
    """Match model - stores all match information."""
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String(50), unique=True, nullable=True)  # API match ID
    date = Column(DateTime, nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id = Column(String(10), nullable=False)
    
    # Match result (nullable until match is played)
    home_goals = Column(Integer, nullable=True)
    away_goals = Column(Integer, nullable=True)
    home_corners = Column(Integer, nullable=True)
    away_corners = Column(Integer, nullable=True)
    home_cards = Column(Integer, nullable=True)
    away_cards = Column(Integer, nullable=True)
    
    # Referee (optional)
    referee_id = Column(Integer, ForeignKey("referees.id"), nullable=True)
    
    # Match status
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, FINISHED, POSTPONED, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    referee = relationship("Referee", back_populates="matches")
    odds = relationship("Odds", back_populates="match", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="match", cascade="all, delete-orphan")
    bets = relationship("Bet", back_populates="match", cascade="all, delete-orphan")
    
    def __repr__(self):
        home = self.home_team.name if self.home_team else "Home"
        away = self.away_team.name if self.away_team else "Away"
        return f"<Match(id={self.id}, {home} vs {away}, {self.date.strftime('%Y-%m-%d')})>"
    
    @property
    def total_goals(self):
        """Get total goals in the match."""
        if self.home_goals is not None and self.away_goals is not None:
            return self.home_goals + self.away_goals
        return None
    
    @property
    def btts(self):
        """Check if both teams scored."""
        if self.home_goals is not None and self.away_goals is not None:
            return self.home_goals > 0 and self.away_goals > 0
        return None


# ============================================
# TABLE 4: ODDS
# ============================================
class Odds(Base):
    """Odds model - stores bookmaker odds with timestamps."""
    __tablename__ = "odds"
    
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    bookmaker = Column(String(50), nullable=False)  # Bet365, William Hill, etc.
    market = Column(String(50), nullable=False)  # over_under_2_5, btts, etc.
    selection = Column(String(50), nullable=True)  # Over, Under, Yes, No, Home, Draw, Away
    odds = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    match = relationship("Match", back_populates="odds")
    
    def __repr__(self):
        return f"<Odds(match_id={self.match_id}, {self.market}={self.odds:.2f}, {self.bookmaker})>"


# ============================================
# TABLE 5: PREDICTIONS
# ============================================
class Prediction(Base):
    """Model predictions - stores all model predictions."""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    model_name = Column(String(50), nullable=False)  # poisson, xgboost_corners, etc.
    market = Column(String(50), nullable=False)  # What market we're predicting
    predicted_prob = Column(Float, nullable=False)  # Our predicted probability (0-1)
    confidence = Column(Float, nullable=False)  # Model confidence (0-1)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Optional: store additional prediction metadata
    extra_data = Column(String(500), nullable=True)  # JSON string for extra info
    
    # Relationships
    match = relationship("Match", back_populates="predictions")
    
    def __repr__(self):
        return f"<Prediction(match_id={self.match_id}, {self.model_name}, {self.market}, prob={self.predicted_prob:.3f})>"


# ============================================
# TABLE 6: BETS
# ============================================
class Bet(Base):
    """Betting record - tracks all bets placed."""
    __tablename__ = "bets"
    
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    market = Column(String(50), nullable=False)
    selection = Column(String(50), nullable=False)  # What we bet on
    stake = Column(Float, nullable=False)  # Amount staked
    odds = Column(Float, nullable=False)  # Odds at time of bet
    
    # Result (filled in after match)
    result = Column(String(10), nullable=True)  # WON, LOST, VOID
    profit = Column(Float, nullable=True)  # Profit/loss from bet
    
    # Strategy used
    strategy = Column(String(50), nullable=True)  # kelly, value_betting, etc.
    
    # Timestamps
    placed_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="bets")
    
    def __repr__(self):
        status = f"£{self.profit:+.2f}" if self.profit is not None else "PENDING"
        return f"<Bet(match_id={self.match_id}, {self.market}, £{self.stake:.2f}@{self.odds:.2f}, {status})>"
    
    def settle(self, won: bool):
        """
        Settle the bet.
        
        Args:
            won: True if bet won, False if lost
        """
        if won:
            self.result = "WON"
            self.profit = (self.stake * self.odds) - self.stake
        else:
            self.result = "LOST"
            self.profit = -self.stake
        
        self.settled_at = datetime.utcnow()


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_session():
    """Get a new database session."""
    return SessionLocal()


def init_db():
    """Initialise database - create all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create database tables: {e}")
        raise


def drop_all_tables():
    """Drop all tables - USE WITH CAUTION!"""
    logger.warning("⚠️  Dropping all database tables!")
    Base.metadata.drop_all(bind=engine)
    logger.info("✓ All tables dropped")


def get_or_create_team(session, name: str, league_id: str, external_id: int = None):
    """
    Get existing team or create new one.
    
    Args:
        session: Database session
        name: Team name
        league_id: League ID (PL, PD, etc.)
        external_id: External API ID
    
    Returns:
        Team object
    """
    team = session.query(Team).filter_by(name=name).first()
    
    if not team:
        team = Team(name=name, league_id=league_id, external_id=external_id)
        session.add(team)
        session.commit()
        logger.info(f"Created new team: {name}")
    
    return team


def get_or_create_referee(session, name: str):
    """
    Get existing referee or create new one.
    
    Args:
        session: Database session
        name: Referee name
    
    Returns:
        Referee object
    """
    referee = session.query(Referee).filter_by(name=name).first()
    
    if not referee:
        referee = Referee(name=name)
        session.add(referee)
        session.commit()
        logger.info(f"Created new referee: {name}")
    
    return referee


# Create Session alias for convenience
Session = SessionLocal


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    """Test database connection and operations."""
    
    logger.info("Testing database connection...")
    
    # Create all tables
    init_db()
    
    # Test inserting data
    session = Session()
    
    try:
        # Create test teams
        home_team = Team(name="Arsenal", league_id="PL", current_elo=1650)
        away_team = Team(name="Chelsea", league_id="PL", current_elo=1620)
        session.add_all([home_team, away_team])
        session.commit()
        logger.info(f"✓ Created test teams: {home_team}, {away_team}")
        
        # Create test match
        match = Match(
            external_id="12345",
            date=datetime(2024, 12, 15, 15, 0),
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            league_id="PL",
            status="SCHEDULED"
        )
        session.add(match)
        session.commit()
        logger.info(f"✓ Created test match: {match}")
        
        # Create test odds
        odds = Odds(
            match_id=match.id,
            bookmaker="Bet365",
            market="over_under_2_5",
            selection="Over",
            odds=1.85
        )
        session.add(odds)
        session.commit()
        logger.info(f"✓ Created test odds: {odds}")
        
        # Create test prediction
        prediction = Prediction(
            match_id=match.id,
            model_name="poisson",
            market="over_under_2_5",
            predicted_prob=0.62,
            confidence=0.78
        )
        session.add(prediction)
        session.commit()
        logger.info(f"✓ Created test prediction: {prediction}")
        
        # Create test bet
        bet = Bet(
            match_id=match.id,
            market="over_under_2_5",
            selection="Over",
            stake=10.0,
            odds=1.85,
            strategy="value_betting"
        )
        session.add(bet)
        session.commit()
        logger.info(f"✓ Created test bet: {bet}")
        
        # Query everything back
        teams = session.query(Team).all()
        matches = session.query(Match).all()
        all_odds = session.query(Odds).all()
        predictions = session.query(Prediction).all()
        bets = session.query(Bet).all()
        
        logger.info(f"✓ Database contains: {len(teams)} teams, {len(matches)} matches, {len(all_odds)} odds, {len(predictions)} predictions, {len(bets)} bets")
        
        # Clean up test data
        session.delete(bet)
        session.delete(prediction)
        session.delete(odds)
        session.delete(match)
        session.delete(home_team)
        session.delete(away_team)
        session.commit()
        logger.info("✓ Test data cleaned up")
        
        logger.info("✓✓✓ DATABASE TEST COMPLETE! ✓✓✓")
        
    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()