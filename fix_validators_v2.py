# Fix validate_score to handle None properly

with open('src/utils/validators.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the validate_score function
old_function = '''def validate_score(score: int) -> None:
    """Validate a match score."""
    if score is not None and not isinstance(score, int):
        raise ValidationError(f"Score must be an integer, got {type(score)}")
    
    if score < 0:
        raise ValidationError(f"Score cannot be negative, got {score}")
    
    if score > 20:
        raise ValidationError(f"Score suspiciously high: {score}")'''

new_function = '''def validate_score(score: int) -> None:
    """Validate a match score. None is allowed for scheduled matches."""
    # None is valid for scheduled matches
    if score is None:
        return
    
    if not isinstance(score, int):
        raise ValidationError(f"Score must be an integer, got {type(score)}")
    
    if score < 0:
        raise ValidationError(f"Score cannot be negative, got {score}")
    
    if score > 20:
        raise ValidationError(f"Score suspiciously high: {score}")'''

content = content.replace(old_function, new_function)

# Also handle the original version if it exists
old_function2 = '''def validate_score(score: int) -> None:
    """Validate a match score."""
    if not isinstance(score, int):
        raise ValidationError(f"Score must be an integer, got {type(score)}")
    
    if score < 0:
        raise ValidationError(f"Score cannot be negative, got {score}")
    
    if score > 20:
        raise ValidationError(f"Score suspiciously high: {score}")'''

content = content.replace(old_function2, new_function)

with open('src/utils/validators.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ validators.py fixed - None scores now allowed for scheduled matches')
