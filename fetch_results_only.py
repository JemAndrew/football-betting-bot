from src.api.football_data_api import FootballDataAPI
from src.data.database import Session, init_db, Match
from src.data.data_aggregator import DataAggregator
from datetime import datetime, timedelta
import time

print('='*70)
print('⚽ FETCHING FINISHED MATCHES ONLY')
print('='*70)

# Initialize
print('\nInitializing database...')
init_db()
api = FootballDataAPI()
session = Session()
aggregator = DataAggregator(session)

# Fetch last 12 months of FINISHED matches
print('\nFetching last 12 months of results...')
try:
    results = api.get_results(competition_code='PL', days_back=365)
    print(f'✓ Found {len(results)} finished matches')
    
    if results:
        print('\nStoring matches...')
        stored = aggregator.aggregate_matches(results, league_id='PL', source='football-data')
        print(f'✓ Stored {len(stored)} matches')
        
        # Verify
        final_count = session.query(Match).count()
        print(f'\n{"="*70}')
        print(f'✅ COMPLETE! Database now has {final_count} matches')
        print(f'{"="*70}')
    
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
    session.rollback()
finally:
    session.close()
