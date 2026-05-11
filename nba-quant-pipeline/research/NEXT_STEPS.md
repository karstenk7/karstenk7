# Next Steps & Recommendations

## Immediate (run when DB is available)

1. **Run schema inspection** against the live DB:
   ```bash
   python -m research.pipelines.inspect_schema
   ```
   This will validate the schema assumptions and reveal actual row counts,
   especially for `odds_snapshots` (how many games have linked odds data).

2. **Build the dataset**:
   ```bash
   # With odds data
   python -m research.run_baseline

   # Without odds (game history features only)
   python -m research.run_baseline --no-odds
   ```

3. **Diagnose odds linkage quality**: Check what % of `odds_snapshots` rows
   have a non-NULL `historical_game_id`. Low linkage means the Rust scraper's
   fuzzy matching needs tuning, or the odds are for future games not yet in
   `historical_games`.

## Short-term improvements

### Data Quality
- **Add a `team_stats` FK**: `team_stats.team_name` uses full names while
  everything else uses abbreviations. Add a proper FK or a materialized view
  that maps to abbreviation.
- **Per-game team stats**: Currently `team_stats` stores season-to-date snapshots
  per day. For rolling features, we derive them from game-by-game outcomes in
  `historical_games`. Consider backfilling per-game advanced stats (ORTG, DRTG,
  pace) from nba_api game logs for richer features.
- **Odds deduplication audit**: Verify that the dedup window in the Rust scraper
  is working correctly and not dropping genuine line movements.

### Feature Engineering
- **Elo ratings**: Simple Elo system updated game-by-game — strong baseline
  predictor and easy to compute without external data.
- **Home court advantage by team**: Some teams have stronger HCA than others.
  Rolling home win % as a feature.
- **Schedule density**: Games in last 7/14 days, miles traveled (if we add
  venue coordinates).
- **Opponent-adjusted metrics**: Rolling stats weighted by opponent strength.
- **Team stats features**: Once `team_stats` linkage is clean, include
  off_rating, def_rating, net_rating, pace differentials as features.

### Modeling
- **Hyperparameter tuning**: Use time-series cross-validation (expanding window)
  with Optuna or sklearn's TimeSeriesSplit.
- **LightGBM**: Often faster than XGBoost with similar performance.
- **Calibration**: Platt scaling or isotonic regression on model probabilities
  for better calibrated outputs.
- **Stacking**: Blend logistic regression + XGB predictions.

### Evaluation
- **Simulated betting returns**: Given model probabilities and closing odds,
  simulate flat-stake and Kelly betting strategies to estimate ROI.
- **CLV (Closing Line Value)**: Track whether model-identified edges align
  with positive CLV — the gold standard for sharp betting.
- **Brier score**: Adds to log loss as a calibration metric.
- **Season-by-season breakdown**: Evaluate per-season to check for regime shifts.

## Medium-term

- **PyMC Bayesian models**: Hierarchical model with team-level random effects,
  partial pooling across seasons. This is the natural next step after the
  frequentist baselines are established.
- **Live prediction pipeline**: Connect the model to the real-time odds scraper
  so it scores each game as new odds arrive.
- **Feature store**: Persist computed features in a `model_features` table
  to avoid recomputation.
- **Player impact**: Once player_stats linkage is solid, model the impact
  of player availability (injuries, rest days) on team performance.

## Architecture Notes

The current structure is intentionally flat:

```
research/
├── config.py              # Centralized configuration
├── db.py                  # Database access layer
├── run_baseline.py        # Main entry point
├── SCHEMA_AUDIT.md        # Schema documentation
├── NEXT_STEPS.md          # This file
├── requirements.txt       # Python dependencies
├── sql/
│   ├── queries.py         # All SQL in one place
│   └── closing_lines.py   # Closing line extraction & pivoting
├── features/
│   └── engineering.py     # Feature generation
├── models/
│   └── baselines.py       # Logistic Regression, XGBoost
├── evaluation/
│   └── metrics.py         # Evaluation & market comparison
├── pipelines/
│   ├── build_dataset.py   # Dataset construction orchestration
│   └── inspect_schema.py  # Live DB schema inspection
└── outputs/               # Generated artifacts (gitignored)
    ├── modeling_dataset.parquet
    ├── dataset_summary.txt
    ├── evaluation_report.txt
    └── schema_inspection.txt
```

Principles:
- No notebooks in the critical path (reproducibility)
- SQL is centralized, not scattered
- Features, models, evaluation are separate concerns
- One clear entry point (`run_baseline.py`)
- Outputs are saved as files, not ephemeral
