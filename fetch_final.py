from src.api.football_data_api import FootballDataAPI
from src.data.database import Session, init_db, Match
from src.data.data_aggregator import DataAggregator

print('='*70)
print('⚽ FETCHING PREMIER LEAGUE DATA')
print('='*70)

init_db()
api = FootballDataAPI()
session = Session()
aggregator = DataAggregator(session)

print('\nFetching last 400 days of results...')
results = api.get_results(competition_code='PL', days_back=400)
print(f'✓ Found {len(results)} finished matches\n')

print('Storing in database...')
stored = aggregator.aggregate_matches(results, league_id='PL', source='football-data')
print(f'\n✓ Successfully stored {len(stored)} matches!')

# Verify
final_count = session.query(Match).count()
print(f'\n{"="*70}')
print(f'✅ DATABASE NOW HAS {final_count} MATCHES!')
print(f'{"="*70}')

# Show a sample
if final_count > 0:
    sample = session.query(Match).first()
    print(f'\nSample: {sample.home_team.name} {sample.home_goals}-{sample.away_goals} {sample.away_team.name}')
    print(f'Date: {sample.date}')

session.close()
