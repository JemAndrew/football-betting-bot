"""
Status Check Script - Run this to see what you've implemented

This will check which files exist and which are still needed.
"""

import os
from pathlib import Path
from typing import List, Tuple

# ANSI color codes for pretty output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists and is not empty."""
    path = Path(filepath)
    return path.exists() and path.stat().st_size > 0


def check_project_status():
    """Check which files are implemented."""
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}📊 FOOTBALL BETTING BOT - PROJECT STATUS CHECK{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    # Define all required files by phase
    status = {
        "PHASE 1: FOUNDATION": {
            "config/api_config.yaml": False,
            "config/leagues.yaml": False,
            "config/betting_config.yaml": False,
            "config/model_config.yaml": False,
            "src/utils/config_loader.py": False,
            "src/utils/logger.py": False,
            "src/utils/helpers.py": False,
            "src/utils/validators.py": False,
            "src/utils/constants.py": False,
            "src/data/database.py": False,
            ".env": False,
        },
        "PHASE 2: DATA COLLECTION": {
            "src/api/base_api.py": False,
            "src/api/football_data_api.py": False,
            "src/api/odds_api.py": False,
            "src/data/data_aggregator.py": False,
            "src/data/data_cleaner.py": False,
            "src/data/data_validator.py": False,
            "scripts/fetch_historical_data.py": False,
            "scripts/update_data.py": False,
        },
        "PHASE 3: SIMPLE MODELS": {
            "src/features/elo_calculator.py": False,
            "src/features/form_calculator.py": False,
            "src/features/team_features.py": False,
            "src/features/match_features.py": False,
            "src/models/goals_model.py": False,
            "src/models/btts_model.py": False,
        },
        "PHASE 4: BACKTESTING": {
            "src/backtesting/backtest_engine.py": False,
            "src/backtesting/performance_metrics.py": False,
            "src/backtesting/portfolio_simulator.py": False,
        },
    }
    
    # Check each file
    for phase, files in status.items():
        for filepath in files:
            status[phase][filepath] = check_file_exists(filepath)
    
    # Print results
    for phase, files in status.items():
        completed = sum(1 for exists in files.values() if exists)
        total = len(files)
        percentage = (completed / total) * 100 if total > 0 else 0
        
        # Phase header
        if percentage == 100:
            status_icon = f"{GREEN}✅{RESET}"
        elif percentage > 0:
            status_icon = f"{YELLOW}🔵{RESET}"
        else:
            status_icon = f"{RED}⬜{RESET}"
        
        print(f"\n{status_icon} {phase} ({completed}/{total} files - {percentage:.0f}%)")
        print(f"{'─'*70}")
        
        # List files
        for filepath, exists in files.items():
            if exists:
                print(f"  {GREEN}✓{RESET} {filepath}")
            else:
                print(f"  {RED}✗{RESET} {filepath}")
    
    # Overall summary
    total_files = sum(len(files) for files in status.values())
    completed_files = sum(
        sum(1 for exists in files.values() if exists)
        for files in status.values()
    )
    overall_percentage = (completed_files / total_files) * 100
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}📈 OVERALL PROGRESS: {completed_files}/{total_files} files ({overall_percentage:.0f}%){RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    # Determine current phase
    if status["PHASE 1: FOUNDATION"]:
        phase1_complete = all(status["PHASE 1: FOUNDATION"].values())
        if not phase1_complete:
            print(f"{YELLOW}📍 CURRENT PHASE: 1 - Foundation{RESET}")
            print(f"{YELLOW}🎯 NEXT TASK: Complete Phase 1 files{RESET}\n")
            return
    
    if status["PHASE 2: DATA COLLECTION"]:
        phase2_complete = all(status["PHASE 2: DATA COLLECTION"].values())
        if not phase2_complete:
            print(f"{YELLOW}📍 CURRENT PHASE: 2 - Data Collection{RESET}")
            print(f"{YELLOW}🎯 NEXT TASK: Complete Phase 2 files{RESET}\n")
            return
    
    print(f"{GREEN}🎉 Phases 1-2 complete! Ready for Phase 3.{RESET}\n")


def print_next_steps():
    """Print recommended next steps."""
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}🚀 RECOMMENDED NEXT STEPS{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    # Check what's missing
    critical_files = {
        "src/api/base_api.py": "Base API client (retry, rate limiting, caching)",
        "src/api/football_data_api.py": "Football-Data.org API integration",
        "src/api/odds_api.py": "Odds API integration",
        "src/data/data_aggregator.py": "Transform API responses to database models",
        "src/data/data_cleaner.py": "Clean and standardise data",
        "scripts/fetch_historical_data.py": "Fetch 2 seasons of historical data",
    }
    
    missing = []
    for filepath, description in critical_files.items():
        if not check_file_exists(filepath):
            missing.append((filepath, description))
    
    if missing:
        print(f"{YELLOW}📝 Files you need to create:{RESET}\n")
        for i, (filepath, description) in enumerate(missing[:3], 1):  # Show top 3
            print(f"  {i}. {filepath}")
            print(f"     → {description}\n")
    else:
        print(f"{GREEN}✅ All critical files exist!{RESET}\n")
    
    # Database check
    if check_file_exists("data/betting_bot.db"):
        print(f"{GREEN}✅ Database exists{RESET}")
    else:
        print(f"{RED}❌ Database not created yet{RESET}")
        print(f"{YELLOW}   → Run: python -m src.data.database{RESET}\n")
    
    # .env check
    if check_file_exists(".env"):
        print(f"{GREEN}✅ .env file exists{RESET}")
    else:
        print(f"{RED}❌ .env file missing{RESET}")
        print(f"{YELLOW}   → Create .env with API keys{RESET}\n")


if __name__ == "__main__":
    check_project_status()
    print_next_steps()
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}💡 TIP: Run this script anytime to check your progress!{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")