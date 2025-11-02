# Read the validators.py file
with open('src/utils/validators.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the validate_score function
new_lines = []
in_validate_score = False
function_found = False

for i, line in enumerate(lines):
    if 'def validate_score(' in line:
        in_validate_score = True
        function_found = True
        # Write the corrected function
        new_lines.append('def validate_score(score: Optional[int], max_score: int = 20) -> None:\n')
        new_lines.append('    """\n')
        new_lines.append('    Validate a match score.\n')
        new_lines.append('    \n')
        new_lines.append('    Args:\n')
        new_lines.append('        score: Score value (can be None for unavailable data)\n')
        new_lines.append('        max_score: Maximum reasonable score\n')
        new_lines.append('    \n')
        new_lines.append('    Raises:\n')
        new_lines.append('        ValidationError: If score is invalid\n')
        new_lines.append('    """\n')
        new_lines.append('    # None is valid - data might not be available\n')
        new_lines.append('    if score is None:\n')
        new_lines.append('        return\n')
        new_lines.append('    \n')
        new_lines.append('    if not isinstance(score, int):\n')
        new_lines.append('        raise ValidationError(f"Score must be an integer, got {type(score)}")\n')
        new_lines.append('    \n')
        new_lines.append('    if score < 0:\n')
        new_lines.append('        raise ValidationError(f"Score cannot be negative, got {score}")\n')
        new_lines.append('    \n')
        new_lines.append('    if score > max_score:\n')
        new_lines.append('        raise ValidationError(f"Score suspiciously high: {score} (max: {max_score})")\n')
        new_lines.append('\n')
        continue
    
    if in_validate_score:
        # Skip old function body until we hit next function or class
        if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
            in_validate_score = False
            new_lines.append(line)
        elif line.strip().startswith('def ') and 'validate_score' not in line:
            in_validate_score = False
            new_lines.append(line)
        continue
    
    new_lines.append(line)

if function_found:
    # Write back
    with open('src/utils/validators.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('✓ validators.py fixed!')
    print('  - validate_score() now handles None properly')
else:
    print('✗ Could not find validate_score function')
