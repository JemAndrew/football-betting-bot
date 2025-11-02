from src.api.football_data_api import FootballDataAPI
from src.data.database import Session, init_db, Match
import json

print('='*70)
print('DEBUG: What is the API actually returning?')
print('='*70)

api = FootballDataAPI()

# Fetch results
print('\nFetching results...')
results = api.get_results(competition_code='PL', days_back=400)
print(f'API returned {len(results)} matches\n')

if results:
    # Show first match raw data
    print('First match (raw JSON):')
    print(json.dumps(results[0], indent=2, default=str))
    print('\n' + '='*70)
    
    # Check status
    statuses = {}
    for m in results:
        status = m.get('status', 'UNKNOWN')
        statuses[status] = statuses.get(status, 0) + 1
    
    print('\nMatch statuses:')
    for status, count in statuses.items():
        print(f'  {status}: {count} matches')
    
    # Check scores
    print('\nScore check:')
    with_scores = 0
    without_scores = 0
    for m in results:
        score = m.get('score', {})
        ft = score.get('fullTime', {})
        if ft.get('home') is not None and ft.get('away') is not None:
            with_scores += 1
        else:
            without_scores += 1
    
    print(f'  With scores: {with_scores}')
    print(f'  Without scores: {without_scores}')
    
    # Now try to process ONE match manually
    print('\n' + '='*70)
    print('Trying to process first match manually...')
    print('='*70)
    
    from src.data.data_aggregator import DataAggregator
    
    init_db()
    session = Session()
    aggregator = DataAggregator(session)
    
    try:
        # Try to parse the first finished match
        first_finished = None
        for m in results:
            if m.get('status') == 'FINISHED':
                first_finished = m
                break
        
        if first_finished:
            print('\nProcessing first FINISHED match...')
            print(f"  {first_finished['homeTeam']['name']} vs {first_finished['awayTeam']['name']}")
            
            # Call the internal parser
            match_data = aggregator._parse_football_data_match(first_finished, 'PL')
            print('\nParsed data:')
            for key, value in match_data.items():
                print(f'  {key}: {value}')
            
            # Try validation
            print('\nValidating...')
            from src.utils.validators import validate_match_data
            try:
                validate_match_data(match_data)
                print('✓ Validation passed!')
            except Exception as e:
                print(f'✗ Validation failed: {e}')
                import traceback
                traceback.print_exc()
        else:
            print('No FINISHED matches found!')
    
    except Exception as e:
        print(f'\n✗ Error during manual processing: {e}')
        import traceback
        traceback.print_exc()
    finally:
        session.close()
else:
    print('No matches returned from API!')
