-- Recreate historical_games / odds_snapshots team FKs as composite
-- (league, team) against the new teams(league, abbreviation) key, now that
-- teams' PK is composite (migration 004). Adds a `league` column to each
-- table to drive the join — separate from odds_snapshots.sport, which is
-- the Odds API's own sport_key string (e.g. 'basketball_nba').
-- Run: psql -U postgres -d nba_quant -f migrations/005_composite_team_fk.sql

BEGIN;

ALTER TABLE historical_games
    ADD COLUMN IF NOT EXISTS league VARCHAR(10) NOT NULL DEFAULT 'nba';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'historical_games_home_team_fkey'
    ) THEN
        ALTER TABLE historical_games
            ADD CONSTRAINT historical_games_home_team_fkey
                FOREIGN KEY (league, home_team) REFERENCES teams (league, abbreviation);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'historical_games_away_team_fkey'
    ) THEN
        ALTER TABLE historical_games
            ADD CONSTRAINT historical_games_away_team_fkey
                FOREIGN KEY (league, away_team) REFERENCES teams (league, abbreviation);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_historical_games_league ON historical_games (league);

ALTER TABLE odds_snapshots
    ADD COLUMN IF NOT EXISTS league VARCHAR(10) NOT NULL DEFAULT 'nba';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'odds_snapshots_home_team_fkey'
    ) THEN
        ALTER TABLE odds_snapshots
            ADD CONSTRAINT odds_snapshots_home_team_fkey
                FOREIGN KEY (league, home_team) REFERENCES teams (league, abbreviation);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'odds_snapshots_away_team_fkey'
    ) THEN
        ALTER TABLE odds_snapshots
            ADD CONSTRAINT odds_snapshots_away_team_fkey
                FOREIGN KEY (league, away_team) REFERENCES teams (league, abbreviation);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_odds_league ON odds_snapshots (league);

-- historical_games.game_id VARCHAR(20) comfortably fits nflverse's
-- "YYYY_WW_AWAY_HOME" game id format (max observed length ~15 chars),
-- so no column width change is needed here.

COMMIT;
