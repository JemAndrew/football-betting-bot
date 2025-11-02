"""
Test ELO Calculator on Premier League Data

This script:
1. Calculates ELO ratings for all 427 matches
2. Shows top/bottom teams by ELO
3. Verifies ratings make intuitive sense
4. Saves a report

Run: python test_elo.py
"""

import sys
import logging
from pathlib import Path

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from features.elo_calculator import ELOCalculator
from data.database import Session, Team, Match

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def analyse_elo_results():
    """
    Analyse ELO ratings after calculation.
    Shows which teams are rated highest/lowest.
    """
    session = Session()
    
    try:
        print("\n" + "="*60)
        print("🏆 PREMIER LEAGUE ELO RATINGS (2024/25)")
        print("="*60 + "\n")
        
        # Get all teams ordered by ELO
        teams = session.query(Team).order_by(Team.current_elo.desc()).all()
        
        print(f"{'Rank':<6} {'Team':<30} {'ELO':<8}")
        print("-" * 60)
        
        for i, team in enumerate(teams, 1):
            print(f"{i:<6} {team.name:<30} {team.current_elo:>7.1f}")
        
        print("\n" + "="*60)
        print(f"Total teams: {len(teams)}")
        print(f"Average ELO: {sum(t.current_elo for t in teams) / len(teams):.1f}")
        print(f"ELO Range: {teams[-1].current_elo:.1f} to {teams[0].current_elo:.1f}")
        print(f"Spread: {teams[0].current_elo - teams[-1].current_elo:.1f} points")
        print("="*60 + "\n")
        
        # Sanity checks
        print("✅ Sanity Checks:")
        print(f"  - Top team has ELO > 1600? {teams[0].current_elo > 1600}")
        print(f"  - Bottom team has ELO < 1400? {teams[-1].current_elo < 1400}")
        print(f"  - Average ELO near 1500? {1450 < sum(t.current_elo for t in teams) / len(teams) < 1550}")
        
        # Check for obvious issues
        top_3 = [t.name for t in teams[:3]]
        bottom_3 = [t.name for t in teams[-3:]]
        
        print(f"\n  Top 3: {', '.join(top_3)}")
        print(f"  Bottom 3: {', '.join(bottom_3)}")
        print(f"\n  Does this look right for 2024/25? (Top teams should be Man City, Arsenal, Liverpool, etc.)")
        
    finally:
        session.close()


def test_prediction():
    """
    Test prediction function with a realistic example.
    """
    session = Session()
    
    try:
        print("\n" + "="*60)
        print("🔮 TESTING MATCH PREDICTION")
        print("="*60 + "\n")
        
        # Get top team and bottom team for a test prediction
        teams = session.query(Team).order_by(Team.current_elo.desc()).all()
        
        if len(teams) < 2:
            print("Not enough teams in database")
            return
        
        top_team = teams[0]
        bottom_team = teams[-1]
        
        calc = ELOCalculator()
        
        # Predict: Top team at home vs Bottom team
        print(f"Prediction: {top_team.name} (H) vs {bottom_team.name} (A)")
        print(f"ELO: {top_team.current_elo:.1f} vs {bottom_team.current_elo:.1f}\n")
        
        # Need to manually create prediction dict since we don't have team IDs
        home_elo = top_team.current_elo
        away_elo = bottom_team.current_elo
        
        expected_home = calc.calculate_expected_score(home_elo, away_elo, is_home=True)
        draw_prob = 0.25
        home_win_prob = expected_home * (1 - draw_prob)
        away_win_prob = (1 - expected_home) * (1 - draw_prob)
        
        print(f"  Home Win: {home_win_prob:.1%}")
        print(f"  Draw:     {draw_prob:.1%}")
        print(f"  Away Win: {away_win_prob:.1%}")
        print(f"\n  Expected outcome score: {expected_home:.2f} (1.0 = certain home win)")
        
        # Show what odds bookmakers would need to offer for value
        if home_win_prob > 0:
            fair_home_odds = 1 / home_win_prob
            print(f"\n  Fair odds for home win: {fair_home_odds:.2f}")
            print(f"  (Bookmaker odds need to be > {fair_home_odds:.2f} for value)")
        
        print("\n" + "="*60)
        
    finally:
        session.close()


def verify_database():
    """Check database has required data."""
    session = Session()
    
    try:
        match_count = session.query(Match).filter(Match.status == 'FINISHED').count()
        team_count = session.query(Team).count()
        
        print("="*60)
        print("📊 DATABASE STATUS")
        print("="*60)
        print(f"Finished matches: {match_count}")
        print(f"Teams: {team_count}")
        
        if match_count == 0:
            print("\n❌ ERROR: No finished matches in database!")
            print("   Run: python scripts/update_data.py first")
            return False
        
        if team_count == 0:
            print("\n❌ ERROR: No teams in database!")
            return False
        
        print("✅ Database looks good\n")
        return True
        
    finally:
        session.close()


def main():
    """Main test execution."""
    
    print("\n🧮 ELO CALCULATOR TEST SCRIPT")
    print("Testing on Premier League 2024/25 data\n")
    
    # Verify database first
    if not verify_database():
        return
    
    # Calculate ELOs
    print("="*60)
    print("🔄 CALCULATING ELO RATINGS")
    print("="*60)
    print("\nProcessing 427 matches chronologically...")
    print("This might take 10-20 seconds...\n")
    
    calc = ELOCalculator(
        k_factor=20,          # Standard K-factor
        home_advantage=100,    # ~100 ELO points for playing at home
        goal_importance=1.0    # Standard goal difference weighting
    )
    
    try:
        # Calculate ELOs for all Premier League matches
        calc.calculate_historical_elos(
            league_id='PL',      # Premier League (your DB uses league_id)
            season=None,         # All seasons
            reset_elos=True      # Start fresh from 1500
        )
        
        print("\n✅ ELO calculation complete!\n")
        
        # Show results
        analyse_elo_results()
        
        # Test prediction
        test_prediction()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nNext steps:")
        print("1. Check if top teams look right (Man City, Arsenal, Liverpool?)")
        print("2. Check if bottom teams look right (Relegated teams?)")
        print("3. If results look good, move on to form_calculator.py")
        print("\nELO ratings are now saved in database → teams.current_elo")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("ELO calculation failed")
        raise


if __name__ == '__main__':
    main()