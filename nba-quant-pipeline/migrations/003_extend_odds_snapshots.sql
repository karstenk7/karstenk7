-- Extend odds_snapshots for multi-sport support and historical game linking.
-- Run: psql -U postgres -d nba_quant -f migrations/003_extend_odds_snapshots.sql

BEGIN;

ALTER TABLE odds_snapshots
    ADD COLUMN IF NOT EXISTS sport VARCHAR(50) NOT NULL DEFAULT 'basketball_nba';

ALTER TABLE odds_snapshots
    ADD COLUMN IF NOT EXISTS historical_game_id VARCHAR(20) REFERENCES historical_games(game_id);

CREATE INDEX IF NOT EXISTS idx_odds_sport     ON odds_snapshots (sport);
CREATE INDEX IF NOT EXISTS idx_odds_hist_game ON odds_snapshots (historical_game_id);

COMMIT;
