
# Data Directory Structure

## Raw Data
Contains unprocessed data directly from APIs. Never modify files in this directory manually.

### Subdirectories:
- **fixtures/**: Upcoming and past match fixtures
- **odds/**: Current odds from various bookmakers
- **team_stats/**: Team performance statistics
- **referee_stats/**: Referee historical data

## Processed Data
Cleaned and processed data ready for feature engineering and modelling.

### Subdirectories:
- **features/**: Engineered features for ML models
- **training/**: Training datasets
- **predictions/**: Model predictions and outputs

## Historical Data
Long-term storage of historical results and odds for backtesting.

### Subdirectories:
- **results/**: Historical match results
- **odds_history/**: Historical odds movements

## Cache
Temporary cache to reduce API calls. Safe to delete.

---

**Note**: All subdirectories are git-ignored except for `.gitkeep` files.
"@ | Out-File -FilePath "football-betting-bot/data/README.md" -Encoding utf8

