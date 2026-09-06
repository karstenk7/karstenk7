-- League-specific NFL stat tables. A shared wide table with NBA's basketball
-- vocabulary (fg3a, pace, off_rating, ...) doesn't translate to football, so
-- these mirror team_stats/player_stats structurally but with NFL columns,
-- rather than bolting NULL-heavy columns onto the existing NBA tables.
-- Run: psql -U postgres -d nba_quant -f migrations/006_nfl_stats_tables.sql

BEGIN;

CREATE TABLE IF NOT EXISTS nfl_team_stats (
    team_abbr                VARCHAR(5)   NOT NULL,
    game_date                DATE         NOT NULL,
    season                   VARCHAR(10)  NOT NULL,
    wins                     INTEGER,
    losses                   INTEGER,
    ties                     INTEGER,
    win_pct                  DOUBLE PRECISION,
    points_per_game          DOUBLE PRECISION,
    points_allowed_per_game  DOUBLE PRECISION,
    yards_per_play           DOUBLE PRECISION,
    pass_epa_per_play        DOUBLE PRECISION,
    rush_epa_per_play        DOUBLE PRECISION,
    third_down_pct           DOUBLE PRECISION,
    turnover_margin          DOUBLE PRECISION,
    PRIMARY KEY (team_abbr, game_date)
);

CREATE INDEX IF NOT EXISTS idx_nfl_team_stats_season ON nfl_team_stats (season);

CREATE TABLE IF NOT EXISTS nfl_player_stats (
    player_name        VARCHAR(100) NOT NULL,
    team_abbr          VARCHAR(5)   NOT NULL,
    position           VARCHAR(5),
    game_date          DATE         NOT NULL,
    season             VARCHAR(10)  NOT NULL,
    passing_yards      DOUBLE PRECISION,
    passing_tds        DOUBLE PRECISION,
    rushing_yards      DOUBLE PRECISION,
    rushing_tds        DOUBLE PRECISION,
    receiving_yards    DOUBLE PRECISION,
    receiving_tds      DOUBLE PRECISION,
    receptions         DOUBLE PRECISION,
    epa_per_play       DOUBLE PRECISION,
    PRIMARY KEY (player_name, game_date)
);

CREATE INDEX IF NOT EXISTS idx_nfl_player_stats_season ON nfl_player_stats (season);
CREATE INDEX IF NOT EXISTS idx_nfl_player_stats_team   ON nfl_player_stats (team_abbr, game_date);

COMMIT;
