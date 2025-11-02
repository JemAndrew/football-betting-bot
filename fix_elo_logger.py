"""
Quick Fix for ELO Calculator Logger Import

Run this to fix the import error:
python fix_elo_logger.py
"""

import os
import sys

# Path to elo_calculator.py
elo_file = 'src/features/elo_calculator.py'

print("🔧 Fixing ELO Calculator Logger Import\n")

if not os.path.exists(elo_file):
    print(f"❌ ERROR: {elo_file} not found!")
    print("   Make sure you're in the project root directory")
    sys.exit(1)

# Read the file
with open(elo_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the import - replace the problematic line with a simple logger setup
old_import = "from src.utils.logger import get_logger"
new_import = """# Simple logger setup that works with any system
import logging
def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger"""

if old_import in content:
    content = content.replace(old_import, new_import)
    
    # Write back
    with open(elo_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Fixed logger import in {elo_file}")
    print("\nNow try running:")
    print("  python test_elo.py")
else:
    print("⚠️  Import already fixed or file format different")
    print("   Manual fix needed - see below:\n")
    print("In src/features/elo_calculator.py, replace line 26:")
    print("  from src.utils.logger import get_logger")
    print("\nWith:")
    print("  import logging")
    print("  logger = logging.getLogger(__name__)")

print("\n✅ Done!")