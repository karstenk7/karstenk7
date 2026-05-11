# Cursor Agent Prompt — Post-Bootstrap Analysis

Feed this to Cursor CLI after running `bash research/bootstrap.sh`.

---

## Context

I have an NBA quant pipeline with:
- A Rust odds scraper persisting live sportsbook data to PostgreSQL
- Historical NBA game data backfilled from nba_api (2015-2024)
- A Python research pipeline in `/research` that builds a modeling dataset and trains baseline models

The bootstrap script just ran and produced outputs in `research/outputs/`.

## Your Tasks

1. **Read the outputs** — inspect `research/outputs/schema_inspection.txt`, `dataset_summary.txt`, and `evaluation_report.txt` to understand what we have.

2. **Diagnose data quality issues**:
   - How many historical games have linked odds data (`historical_game_id` not null)?
   - What's the distribution of snapshots per game?
   - Are there bookmaker coverage gaps?
   - Run diagnostic queries against the live database.

3. **Analyze baseline model performance**:
   - Are the models beating the market (sportsbook implied probabilities)?
   - Which features are most important?
   - Is there signal beyond what the odds already capture?

4. **Identify quick wins**:
   - Are there obvious feature engineering improvements?
   - Is the closing line extraction working correctly?
   - Should we adjust rolling windows or add new features?

5. **If models are underperforming the market** (expected for v1):
   - That's fine — the market is very efficient.
   - Focus on identifying WHERE the model disagrees with the market most, and whether those disagreements have any predictive value.
   - Consider adding Elo ratings as a feature.

6. **Propose next iteration** with specific code changes.

Important: Do NOT build deep learning, transformers, RL, or PyMC yet. Stick to the scikit-learn / XGBoost stack. Focus on data quality and feature engineering over model complexity.
