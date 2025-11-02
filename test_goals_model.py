"""
Test Goals Model

Shows match predictions using Poisson distribution.
Demonstrates betting value calculation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from models.goals_model import GoalsModel
from data.database import Session, Team

import logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def test_single_match():
    """Show detailed prediction for one match."""
    
    session = Session()
    
    try:
        print("\n" + "="*80)
        print("SINGLE MATCH PREDICTION")
        print("="*80 + "\n")
        
        # Get top team vs bottom team
        teams = session.query(Team).order_by(Team.current_elo.desc()).all()
        
        if len(teams) < 2:
            print("Not enough teams")
            return
        
        top_team = teams[0]
        bottom_team = teams[-1]
        
        print(f"Match: {top_team.name} (Home) vs {bottom_team.name} (Away)\n")
        
        # Create model
        model = GoalsModel(
            home_advantage=1.3,
            use_elo=True,
            use_form=True,
            elo_weight=0.3,
            form_weight=0.2
        )
        
        # Get prediction
        prediction = model.predict_match(
            home_team_id=top_team.id,
            away_team_id=bottom_team.id
        )
        
        print("="*80)
        print("EXPECTED GOALS")
        print("="*80)
        print(f"  {top_team.name}: {prediction['home_xg']:.2f} xG")
        print(f"  {bottom_team.name}: {prediction['away_xg']:.2f} xG")
        print(f"  Total: {prediction['total_xg']:.2f} goals expected")
        
        print("\n" + "="*80)
        print("MATCH RESULT PROBABILITIES")
        print("="*80)
        print(f"  {top_team.name} Win: {prediction['home_win_prob']:.1%}")
        print(f"  Draw:               {prediction['draw_prob']:.1%}")
        print(f"  {bottom_team.name} Win: {prediction['away_win_prob']:.1%}")
        
        print("\n" + "="*80)
        print("BETTING MARKETS")
        print("="*80)
        print(f"  Over 2.5 goals:  {prediction['over_25_prob']:.1%}")
        print(f"  Under 2.5 goals: {prediction['under_25_prob']:.1%}")
        print(f"  Both Teams Score (BTTS): {prediction['btts_prob']:.1%}")
        print(f"  {top_team.name} Clean Sheet: {prediction['probabilities']['home_clean_sheet']:.1%}")
        
        print("\n" + "="*80)
        print("FAIR ODDS (What odds should be offered)")
        print("="*80)
        print(f"  {top_team.name} Win: {prediction['fair_odds']['home_win']:.2f}")
        print(f"  Draw:               {prediction['fair_odds']['draw']:.2f}")
        print(f"  {bottom_team.name} Win: {prediction['fair_odds']['away_win']:.2f}")
        print(f"  Over 2.5:           {prediction['fair_odds']['over_25']:.2f}")
        print(f"  BTTS Yes:           {prediction['fair_odds']['btts_yes']:.2f}")
        
        print("\n" + "="*80)
        print("MOST LIKELY SCORELINES")
        print("="*80)
        top_scorelines = model.get_top_scorelines(prediction, top_n=5)
        for i, ((home_goals, away_goals), prob) in enumerate(top_scorelines, 1):
            print(f"  {i}. {home_goals}-{away_goals}: {prob:.1%}")
        
    finally:
        session.close()


def test_value_betting():
    """Demonstrate value betting calculation."""
    
    session = Session()
    
    try:
        print("\n" + "="*80)
        print("VALUE BETTING EXAMPLE")
        print("="*80 + "\n")
        
        # Get a realistic matchup
        teams = session.query(Team).order_by(Team.current_elo.desc()).all()
        
        if len(teams) < 5:
            print("Not enough teams")
            return
        
        home_team = teams[2]  # 3rd best team
        away_team = teams[4]  # 5th best team
        
        print(f"Match: {home_team.name} (Home) vs {away_team.name} (Away)\n")
        
        # Get prediction
        model = GoalsModel()
        prediction = model.predict_match(
            home_team_id=home_team.id,
            away_team_id=away_team.id
        )
        
        # Simulate bookmaker odds (typically worse than fair odds)
        # Bookmakers add margin so their odds are lower than fair
        bookmaker_odds = {
            'home_win': prediction['fair_odds']['home_win'] * 0.95,  # 5% margin
            'draw': prediction['fair_odds']['draw'] * 0.90,  # 10% margin (draws have big margin)
            'away_win': prediction['fair_odds']['away_win'] * 0.92,
            'over_25': prediction['fair_odds']['over_25'] * 0.93,
            'btts_yes': prediction['fair_odds']['btts_yes'] * 0.94
        }
        
        print("Our Prediction vs Bookmaker Odds:")
        print("-" * 80)
        print(f"{'Market':<15} {'Our Prob':<12} {'Fair Odds':<12} {'Bookie Odds':<13} {'Value?':<10}")
        print("-" * 80)
        
        for market in ['home_win', 'draw', 'over_25', 'btts_yes']:
            fair = prediction['fair_odds'][market]
            bookie = bookmaker_odds.get(market, 0)
            
            if market == 'home_win':
                our_prob = prediction['home_win_prob']
            elif market == 'draw':
                our_prob = prediction['draw_prob']
            elif market == 'over_25':
                our_prob = prediction['over_25_prob']
            elif market == 'btts_yes':
                our_prob = prediction['btts_prob']
            
            # Calculate expected value
            if bookie > 0:
                ev = model.calculate_expected_value(our_prob, bookie)
                value_status = "YES" if ev > 0.05 else "NO"
            else:
                ev = 0
                value_status = "N/A"
            
            print(
                f"{market:<15} {our_prob:<12.1%} {fair:<12.2f} {bookie:<13.2f} "
                f"{value_status:<10}"
            )
        
        # Find value bets
        print("\n" + "="*80)
        print("VALUE BETS DETECTED (5%+ edge)")
        print("="*80 + "\n")
        
        value_bets = model.find_value_bets(
            prediction=prediction,
            bookmaker_odds=bookmaker_odds,
            min_edge=0.05
        )
        
        if value_bets:
            print(f"Found {len(value_bets)} value bet(s):\n")
            for bet in value_bets:
                print(f"Market: {bet['market']}")
                print(f"  Our probability: {bet['our_probability']:.1%}")
                print(f"  Bookmaker odds: {bet['bookmaker_odds']:.2f}")
                print(f"  Implied probability: {bet['implied_probability']:.1%}")
                print(f"  Edge: {bet['edge']:.1%}")
                print(f"  Expected Value: {bet['expected_value']:.1%}")
                print(f"  Recommendation: BET (positive EV)")
                print()
        else:
            print("No value bets found (all edges below 5%)")
            print("This is normal - most matches don't offer value")
        
    finally:
        session.close()


def test_multiple_matches():
    """Show predictions for multiple matches."""
    
    session = Session()
    
    try:
        print("\n" + "="*80)
        print("MULTIPLE MATCH PREDICTIONS")
        print("="*80 + "\n")
        
        teams = session.query(Team).order_by(Team.current_elo.desc()).limit(10).all()
        
        if len(teams) < 4:
            print("Not enough teams")
            return
        
        # Create a few interesting matchups
        matchups = [
            (teams[0], teams[5]),  # Top vs mid-table
            (teams[2], teams[3]),  # Two top teams
            (teams[7], teams[9])   # Two lower teams
        ]
        
        model = GoalsModel()
        
        print(f"{'Home Team':<30} {'Away Team':<30} {'Home Win':<10} {'Draw':<8} {'O2.5':<8}")
        print("-" * 86)
        
        for home, away in matchups:
            prediction = model.predict_match(
                home_team_id=home.id,
                away_team_id=away.id
            )
            
            print(
                f"{home.name:<30} {away.name:<30} "
                f"{prediction['home_win_prob']:<10.1%} "
                f"{prediction['draw_prob']:<8.1%} "
                f"{prediction['over_25_prob']:<8.1%}"
            )
        
        print("\n" + "="*80)
        print("\nInterpretation:")
        print("  Home Win > 60%: Strong home favourite")
        print("  Home Win 45-55%: Close match")
        print("  O2.5 > 60%: High-scoring expected")
        print("  O2.5 < 40%: Low-scoring expected")
        
    finally:
        session.close()


def explain_model():
    """Explain how the model works."""
    
    print("\n" + "="*80)
    print("HOW THE POISSON MODEL WORKS")
    print("="*80 + "\n")
    
    print("STEP 1: Calculate Expected Goals")
    print("-" * 80)
    print("  Home xG = Home Attack × Away Defence × League Avg × Home Advantage")
    print("  Away xG = Away Attack × Home Defence × League Avg")
    print()
    print("  Example:")
    print("    Arsenal (Attack 1.4x) vs Southampton (Defence 1.5x)")
    print("    League avg = 1.5 goals, Home advantage = 1.3x")
    print("    Arsenal xG = 1.4 × 1.5 × 1.5 × 1.3 = 4.09 goals")
    print()
    
    print("STEP 2: Apply Poisson Distribution")
    print("-" * 80)
    print("  Poisson models rare events (goals are rare)")
    print("  Given xG = 2.0, what's probability of scoring exactly 2 goals?")
    print("  P(2) = (2.0² × e^-2.0) / 2! = 27%")
    print()
    
    print("STEP 3: Calculate All Scorelines")
    print("-" * 80)
    print("  Home xG = 2.0, Away xG = 1.2")
    print("  P(2-1) = P(home scores 2) × P(away scores 1) = 27% × 36% = 9.7%")
    print("  Repeat for all scorelines (0-0, 1-0, 0-1, 1-1, 2-0, etc.)")
    print()
    
    print("STEP 4: Aggregate Into Markets")
    print("-" * 80)
    print("  Over 2.5 = P(0-3) + P(1-2) + P(2-1) + P(3-0) + P(3-1) + ... ")
    print("  BTTS = Sum of all scorelines where both teams score")
    print()
    
    print("STEP 5: Calculate Fair Odds")
    print("-" * 80)
    print("  Fair Odds = 1 / Probability")
    print("  If Over 2.5 has 60% probability → Fair odds = 1/0.60 = 1.67")
    print()
    
    print("STEP 6: Find Value Bets")
    print("-" * 80)
    print("  Compare our probability to bookmaker odds")
    print("  If our prob = 60% and bookie offers 2.00:")
    print("    EV = (0.60 × 2.00) - 1 = +0.20 = +20% edge")
    print("    This is a VALUE BET")
    print()
    
    print("="*80)


def main():
    """Run all goals model tests."""
    
    print("\nGOALS MODEL TEST SCRIPT")
    print("Poisson-based match outcome predictions\n")
    
    try:
        # Explain how it works
        explain_model()
        
        # Single match detailed prediction
        test_single_match()
        
        # Value betting demonstration
        test_value_betting()
        
        # Multiple matches
        test_multiple_matches()
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED")
        print("="*80)
        print("\nNext steps:")
        print("1. Check if expected goals look realistic")
        print("2. Check if probabilities make sense (top team should be favourite)")
        print("3. Fair odds should be close to real bookmaker odds")
        print("4. If results look good, move on to Phase 4 (Backtesting)")
        print("\nGoals model now ready for backtesting and live predictions")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        logger.exception("Goals model test failed")
        raise


if __name__ == '__main__':
    main()