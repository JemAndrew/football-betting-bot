from datetime import datetime, date as date_type
from typing import Union

# Read helpers.py
with open('src/utils/helpers.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the format_date function and fix it
new_lines = []
in_format_date = False
skip_until_next_def = False

for i, line in enumerate(lines):
    if 'def format_date(' in line:
        in_format_date = True
        skip_until_next_def = True
        # Write the fixed function
        new_lines.append('def format_date(date: Union[str, datetime], format_str: str = "%Y-%m-%d") -> str:\n')
        new_lines.append('    """\n')
        new_lines.append('    Format a date consistently.\n')
        new_lines.append('    \n')
        new_lines.append('    Args:\n')
        new_lines.append('        date: Date as string, datetime, or date object\n')
        new_lines.append('        format_str: Desired output format\n')
        new_lines.append('    \n')
        new_lines.append('    Returns:\n')
        new_lines.append('        Formatted date string\n')
        new_lines.append('    """\n')
        new_lines.append('    from datetime import date as date_type\n')
        new_lines.append('    \n')
        new_lines.append('    if isinstance(date, str):\n')
        new_lines.append('        # Try parsing common formats\n')
        new_lines.append('        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%SZ"]:\n')
        new_lines.append('            try:\n')
        new_lines.append('                date = datetime.strptime(date, fmt)\n')
        new_lines.append('                break\n')
        new_lines.append('            except ValueError:\n')
        new_lines.append('                continue\n')
        new_lines.append('    \n')
        new_lines.append('    if isinstance(date, (datetime, date_type)):\n')
        new_lines.append('        return date.strftime(format_str)\n')
        new_lines.append('    \n')
        new_lines.append('    raise ValueError(f"Could not parse date: {date}")\n')
        new_lines.append('\n')
        continue
    
    if skip_until_next_def:
        # Skip lines until we hit the next function or end of function
        if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
            skip_until_next_def = False
            new_lines.append(line)
        elif line.strip().startswith('def ') and 'format_date' not in line:
            skip_until_next_def = False
            new_lines.append('\n')
            new_lines.append(line)
        continue
    
    new_lines.append(line)

# Write back
with open('src/utils/helpers.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('✓ helpers.py fixed successfully!')
