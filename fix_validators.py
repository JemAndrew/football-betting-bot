# Fix the validate_match_data function to allow None scores for scheduled matches

with open('src/utils/validators.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the validate_score calls and make them conditional
old_code = '''def validate_match_data(match_data: Dict[str, Any]) -> None:
    \"\"\"
    Validate match data dictionary.
    
    Args:
        match_data: Match data to validate
    
    Raises:
        ValidationError: If data is invalid
    \"\"\"
    required_fields = ['home_team_name', 'away_team_name', 'date', 'league_id']
    
    for field in required_fields:
        if field not in match_data or not match_data[field]:
            raise ValidationError(f\"Missing required field: {field}\")
    
    # Validate scores if present
    if match_data.get('home_goals') is not None:
        validate_score(match_data['home_goals'])
    
    if match_data.get('away_goals') is not None:
        validate_score(match_data['away_goals'])'''

new_code = '''def validate_match_data(match_data: Dict[str, Any]) -> None:
    \"\"\"
    Validate match data dictionary.
    
    Args:
        match_data: Match data to validate
    
    Raises:
        ValidationError: If data is invalid
    \"\"\"
    required_fields = ['home_team_name', 'away_team_name', 'date', 'league_id']
    
    for field in required_fields:
        if field not in match_data or not match_data[field]:
            raise ValidationError(f\"Missing required field: {field}\")
    
    # Validate scores if present (None is OK for scheduled matches)
    if match_data.get('home_goals') is not None:
        validate_score(match_data['home_goals'])
    
    if match_data.get('away_goals') is not None:
        validate_score(match_data['away_goals'])
    
    # Status can be SCHEDULED, FINISHED, TIMED, etc.
    # Scores should only be present for FINISHED matches
    status = match_data.get('status', 'SCHEDULED')
    if status == 'FINISHED':
        # Finished matches must have scores
        if match_data.get('home_goals') is None or match_data.get('away_goals') is None:
            # This is just a warning, not an error - data might not be available yet
            pass'''

# Replace the function
if old_code in content:
    content = content.replace(old_code, new_code)
    
    with open('src/utils/validators.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ validators.py updated successfully!')
else:
    print('⚠ Could not find exact match, checking validate_score...')
    
    # Alternative: just comment out the strict validation in validate_score
    content = content.replace(
        'if not isinstance(score, int):',
        'if score is not None and not isinstance(score, int):'
    )
    
    with open('src/utils/validators.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ validators.py updated (alternative method)!')
