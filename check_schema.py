"""
Check Database Schema

This will show us the exact field names in your Match table.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data.database import Session, Match, Team
from sqlalchemy import inspect

session = Session()

print("🔍 Checking Database Schema\n")
print("="*60)

# Check Match table columns
print("📋 Match Table Columns:")
print("-"*60)
inspector = inspect(Match)
for column in inspector.columns:
    print(f"  {column.name:<30} {column.type}")

print("\n" + "="*60)

# Show a sample match to see actual data
print("\n📊 Sample Match Data:")
print("-"*60)
sample = session.query(Match).first()
if sample:
    for key, value in sample.__dict__.items():
        if not key.startswith('_'):
            print(f"  {key:<30} {value}")
else:
    print("  No matches found")

print("\n" + "="*60)

# Check Team table columns
print("\n📋 Team Table Columns:")
print("-"*60)
inspector = inspect(Team)
for column in inspector.columns:
    print(f"  {column.name:<30} {column.type}")

session.close()

print("\n✅ Schema check complete!")
print("\nThis will help us fix the ELO calculator to use the right field names.")