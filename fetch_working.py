from src.api.football_data_api import FootballDataAPI  
from src.data.database import Session, init_db, Match
from src.data.data_aggregator import DataAggregator
import time

print('='*70)
print('⚽ FETCHING FINISHED PREMIER LEAGUE MATCHES')
print('='*70)

# Initialize
init_db()
api = FootballDataAPI()
session = Session()
aggregator = DataAggregator(session)

# Fetch results from last 400 days (should get ~300 matches)
print('\nFetching results from last 400 days...')
print('(This gets only FINISHED matches, no validation issues)\n')

try:
    results = api.get_results(competition_code='PL', days_back=400)
    print(f'✓ API returned {len(results)} finished matches\n')
    
    if results:
        # Filter to only FINISHED status
        finished = [m for m in results if m.get('status') == 'FINISHED']
        print(f'✓ {len(finished)} are confirmed FINISHED\n')
        
        print('Storing in database...')
        stored = aggregator.aggregate_matches(finished, league_id='PL', source='football-data')
        print(f'✓ Successfully stored {len(stored)} matches\n')
        
        # Show sample
        if stored:
            sample = session.query(Match).first()
            print(f'Sample match: {sample.home_team.name} {sample.home_goals}-{sample.away_goals} {sample.away_team.name}')
        
        print(f'\n{"="*70}')
        print(f'✅ SUCCESS! Database has {session.query(Match).count()} matches')
        print(f'{"="*70}')
    else:
        print('⚠ No results returned from API')
        
except Exception as e:
    print(f'\n✗ Error: {e}')
    import traceback
    traceback.print_exc()
    session.rollback()
finally:
    session.close()
