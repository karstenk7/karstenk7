"""SQL query library for the research pipeline.

Each function returns a SQL string (or executes via read_sql).
Keeping SQL centralized avoids scattering queries across modules.
"""

HISTORICAL_GAMES = """
SELECT
    game_id,
    season,
    game_date,
    home_team,
    away_team,
    home_score,
    away_score,
    home_win,
    actual_spread,
    actual_total
FROM historical_games
ORDER BY game_date, game_id
"""

TEAMS = """
SELECT abbreviation, full_name, city, conference
FROM teams
ORDER BY abbreviation
"""

TEAM_STATS = """
SELECT
    ts.team_name,
    ts.game_date,
    ts.season,
    t.abbreviation AS team_abbr,
    ts.wins, ts.losses, ts.win_pct,
    ts.pts_per_game, ts.plus_minus,
    ts.fg3a, ts.fg3_pct,
    ts.off_rating, ts.def_rating, ts.net_rating, ts.pace
FROM team_stats ts
JOIN teams t ON ts.team_name = t.full_name
ORDER BY ts.game_date, ts.team_name
"""

# ------------------------------------------------------------------
# Closing line extraction
#
# For each (historical_game_id, bookmaker, market_type, outcome_name),
# get the LAST snapshot captured BEFORE commence_time.
# This is the "closing line" — the final odds before tip-off.
# ------------------------------------------------------------------

CLOSING_LINES = """
WITH ranked AS (
    SELECT
        os.historical_game_id,
        os.home_team,
        os.away_team,
        os.commence_time,
        os.bookmaker,
        os.market_type,
        os.outcome_name,
        os.price,
        os.point,
        os.captured_at,
        ROW_NUMBER() OVER (
            PARTITION BY os.historical_game_id, os.bookmaker, os.market_type, os.outcome_name
            ORDER BY os.captured_at DESC
        ) AS rn
    FROM odds_snapshots os
    WHERE os.historical_game_id IS NOT NULL
      AND os.captured_at <= os.commence_time
)
SELECT
    historical_game_id,
    home_team,
    away_team,
    commence_time,
    bookmaker,
    market_type,
    outcome_name,
    price,
    point,
    captured_at
FROM ranked
WHERE rn = 1
ORDER BY historical_game_id, bookmaker, market_type
"""

# Earliest snapshot per game (for opening line)
OPENING_LINES = """
WITH ranked AS (
    SELECT
        os.historical_game_id,
        os.bookmaker,
        os.market_type,
        os.outcome_name,
        os.price,
        os.point,
        os.captured_at,
        ROW_NUMBER() OVER (
            PARTITION BY os.historical_game_id, os.bookmaker, os.market_type, os.outcome_name
            ORDER BY os.captured_at ASC
        ) AS rn
    FROM odds_snapshots os
    WHERE os.historical_game_id IS NOT NULL
)
SELECT
    historical_game_id,
    bookmaker,
    market_type,
    outcome_name,
    price  AS open_price,
    point  AS open_point,
    captured_at AS first_captured_at
FROM ranked
WHERE rn = 1
ORDER BY historical_game_id, bookmaker, market_type
"""

# All odds snapshots for a given game (for line movement analysis)
ODDS_TIMELINE = """
SELECT
    os.historical_game_id,
    os.bookmaker,
    os.market_type,
    os.outcome_name,
    os.price,
    os.point,
    os.captured_at,
    os.commence_time
FROM odds_snapshots os
WHERE os.historical_game_id = %(game_id)s
ORDER BY os.captured_at
"""

# Snapshot counts per historical game (diagnostic)
ODDS_COVERAGE = """
SELECT
    os.historical_game_id,
    COUNT(*) AS total_snapshots,
    COUNT(DISTINCT os.bookmaker) AS bookmaker_count,
    MIN(os.captured_at) AS first_snapshot,
    MAX(os.captured_at) AS last_snapshot,
    os.commence_time
FROM odds_snapshots os
WHERE os.historical_game_id IS NOT NULL
GROUP BY os.historical_game_id, os.commence_time
ORDER BY os.commence_time
"""
