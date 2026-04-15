"""Populate current-season team and player stats into PostgreSQL."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from nba_api.stats.endpoints import (
    leaguedashplayerstats,
    leaguedashteamstats,
    teamestimatedmetrics,
)

from data_pipeline.config import get_settings
from data_pipeline.db.insert_games import get_connection

SEASON = "2024-25"

TEAM_STATS_SQL = """
INSERT INTO team_stats (
    team_name, game_date, season,
    wins, losses, win_pct,
    pts_per_game, plus_minus,
    fg3a, fg3_pct,
    off_rating, def_rating, net_rating, pace
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (team_name, game_date) DO UPDATE SET
    wins = EXCLUDED.wins,
    losses = EXCLUDED.losses,
    net_rating = EXCLUDED.net_rating,
    pace = EXCLUDED.pace
"""

PLAYER_STATS_SQL = """
INSERT INTO player_stats (
    player_name, team_name, game_date, season,
    pts_per_game, reb_per_game, ast_per_game,
    minutes_per_game, plus_minus, fg3_pct
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (player_name, game_date) DO UPDATE SET
    pts_per_game = EXCLUDED.pts_per_game,
    minutes_per_game = EXCLUDED.minutes_per_game,
    plus_minus = EXCLUDED.plus_minus
"""


def populate_team_stats(conn) -> int:
    print("Fetching team stats...")
    time.sleep(1)

    basic = leaguedashteamstats.LeagueDashTeamStats(season=SEASON).get_data_frames()[0]
    time.sleep(1)
    advanced = teamestimatedmetrics.TeamEstimatedMetrics(season=SEASON).get_data_frames()[0]

    merged = basic.merge(
        advanced[["TEAM_NAME", "E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING", "E_PACE"]],
        on="TEAM_NAME",
    )

    today = date.today()
    records = [
        (
            row["TEAM_NAME"], today, SEASON,
            row["W"], row["L"], row["W_PCT"],
            row["PTS"], row["PLUS_MINUS"],
            row["FG3A"], row["FG3_PCT"],
            row["E_OFF_RATING"], row["E_DEF_RATING"],
            row["E_NET_RATING"], row["E_PACE"],
        )
        for _, row in merged.iterrows()
    ]

    with conn.cursor() as cur:
        cur.executemany(TEAM_STATS_SQL, records)
        conn.commit()

    print(f"Inserted {len(records)} team records")
    return len(records)


def populate_player_stats(conn) -> int:
    print("Fetching player stats...")
    time.sleep(1)

    stats = leaguedashplayerstats.LeagueDashPlayerStats(season=SEASON).get_data_frames()[0]
    today = date.today()

    records = [
        (
            row["PLAYER_NAME"], row["TEAM_ABBREVIATION"],
            today, SEASON,
            row["PTS"], row["REB"], row["AST"],
            row["MIN"], row["PLUS_MINUS"], row["FG3_PCT"],
        )
        for _, row in stats.iterrows()
    ]

    with conn.cursor() as cur:
        cur.executemany(PLAYER_STATS_SQL, records)
        conn.commit()

    print(f"Inserted {len(records)} player records")
    return len(records)


def main() -> None:
    settings = get_settings()
    conn = get_connection(settings)
    try:
        populate_team_stats(conn)
        populate_player_stats(conn)
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
