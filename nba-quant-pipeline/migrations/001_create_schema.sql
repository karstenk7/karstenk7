-- NBA Quant Pipeline: Full Schema
-- Run: psql -U postgres -d nba_quant -f migrations/001_create_schema.sql

BEGIN;

-- ============================================================
-- Reference table: canonical team identifiers
-- ============================================================
CREATE TABLE IF NOT EXISTS teams (
    abbreviation  VARCHAR(5)   PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL UNIQUE,
    city          VARCHAR(50)  NOT NULL,
    conference    VARCHAR(4)   NOT NULL CHECK (conference IN ('East', 'West'))
);

-- ============================================================
-- Historical game outcomes (backfilled from nba_api)
-- ============================================================
CREATE TABLE IF NOT EXISTS historical_games (
    game_id        VARCHAR(20)  PRIMARY KEY,
    season         VARCHAR(10)  NOT NULL,
    game_date      DATE         NOT NULL,
    home_team      VARCHAR(5)   NOT NULL REFERENCES teams(abbreviation),
    away_team      VARCHAR(5)   NOT NULL REFERENCES teams(abbreviation),
    home_score     INTEGER      NOT NULL,
    away_score     INTEGER      NOT NULL,
    home_win       BOOLEAN      NOT NULL,
    actual_spread  INTEGER      NOT NULL,
    actual_total   INTEGER      NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_historical_games_date    ON historical_games (game_date);
CREATE INDEX IF NOT EXISTS idx_historical_games_season  ON historical_games (season);
CREATE INDEX IF NOT EXISTS idx_historical_games_home    ON historical_games (home_team);
CREATE INDEX IF NOT EXISTS idx_historical_games_away    ON historical_games (away_team);

-- ============================================================
-- Live odds snapshots (populated by Rust scraper)
-- ============================================================
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id              BIGSERIAL    PRIMARY KEY,
    game_id         VARCHAR(64)  NOT NULL,
    commence_time   TIMESTAMPTZ  NOT NULL,
    home_team       VARCHAR(5)   NOT NULL REFERENCES teams(abbreviation),
    away_team       VARCHAR(5)   NOT NULL REFERENCES teams(abbreviation),
    bookmaker       VARCHAR(50)  NOT NULL,
    market_type     VARCHAR(20)  NOT NULL,
    outcome_name    VARCHAR(100) NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    point           DOUBLE PRECISION,
    captured_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_odds_game        ON odds_snapshots (game_id);
CREATE INDEX IF NOT EXISTS idx_odds_captured    ON odds_snapshots (captured_at);
CREATE INDEX IF NOT EXISTS idx_odds_market      ON odds_snapshots (market_type);
CREATE INDEX IF NOT EXISTS idx_odds_bookmaker   ON odds_snapshots (bookmaker, market_type);

-- ============================================================
-- Team aggregate stats (populated by populate_stats.py)
-- ============================================================
CREATE TABLE IF NOT EXISTS team_stats (
    team_name      VARCHAR(100) NOT NULL,
    game_date      DATE         NOT NULL,
    season         VARCHAR(10)  NOT NULL,
    wins           INTEGER,
    losses         INTEGER,
    win_pct        DOUBLE PRECISION,
    pts_per_game   DOUBLE PRECISION,
    plus_minus     DOUBLE PRECISION,
    fg3a           DOUBLE PRECISION,
    fg3_pct        DOUBLE PRECISION,
    off_rating     DOUBLE PRECISION,
    def_rating     DOUBLE PRECISION,
    net_rating     DOUBLE PRECISION,
    pace           DOUBLE PRECISION,
    PRIMARY KEY (team_name, game_date)
);

-- ============================================================
-- Player aggregate stats (populated by populate_stats.py)
-- ============================================================
CREATE TABLE IF NOT EXISTS player_stats (
    player_name      VARCHAR(100) NOT NULL,
    team_name        VARCHAR(10)  NOT NULL,
    game_date        DATE         NOT NULL,
    season           VARCHAR(10)  NOT NULL,
    pts_per_game     DOUBLE PRECISION,
    reb_per_game     DOUBLE PRECISION,
    ast_per_game     DOUBLE PRECISION,
    minutes_per_game DOUBLE PRECISION,
    plus_minus       DOUBLE PRECISION,
    fg3_pct          DOUBLE PRECISION,
    PRIMARY KEY (player_name, game_date)
);

-- ============================================================
-- Pipeline job tracking (observability)
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          BIGSERIAL    PRIMARY KEY,
    job_name    VARCHAR(100) NOT NULL,
    started_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    rows_in     INTEGER,
    rows_out    INTEGER,
    status      VARCHAR(20)  NOT NULL DEFAULT 'running',
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_job ON pipeline_runs (job_name, started_at);

COMMIT;
