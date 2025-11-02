from src.api.football_data_api import FootballDataAPI
from src.data.database import Session, init_db, Match
from src.data.data_aggregator import DataAggregator
from datetime import datetime, timedelta
import time

print('='*70)
print('⚽ FETCHING PREMIER LEAGUE HISTORICAL DATA')
print('='*70)

# Initialize
print('\nInitializing database...')
init_db()
api = FootballDataAPI()
session = Session()
aggregator = DataAggregator(session)

# Fetch 2023/24 and 2024/25 seasons
seasons = [
    ('2023-08-01', '2024-05-31', '2023/24'),
    ('2024-08-01', '2025-05-31', '2024/25')
]

total_matches = 0

for start, end, season_name in seasons:
    print(f'\n{"="*70}')
    print(f'Fetching {season_name} season: {start} to {end}')
    print(f'{"="*70}')
    
    # Fetch in monthly chunks
    current = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')
    season_matches = []
    
    while current < end_date:
        month_end = min(current + timedelta(days=30), end_date)
        
        print(f'\nFetching {current.strftime("%Y-%m-%d")} to {month_end.strftime("%Y-%m-%d")}...')
        
        try:
            matches = api.get_matches(
                competition_code='PL',
                date_from=current.strftime('%Y-%m-%d'),
                date_to=month_end.strftime('%Y-%m-%d')
            )
            print(f'  ✓ Found {len(matches)} matches')
            season_matches.extend(matches)
            
            # Respect rate limit (10 req/min = 6 seconds)
            time.sleep(6)
            
        except Exception as e:
            print(f'  ✗ Error: {e}')
        
        current = month_end
    
    # Store season matches
    if season_matches:
        print(f'\nStoring {len(season_matches)} matches from {season_name}...')
        stored = aggregator.aggregate_matches(season_matches, league_id='PL', source='football-data')
        print(f'✓ Stored {len(stored)} matches')
        total_matches += len(stored)

# Verify
final_count = session.query(Match).count()
print(f'\n{"="*70}')
print(f'✅ COMPLETE! Database now has {final_count} matches')
print(f'{"="*70}')

session.close()
