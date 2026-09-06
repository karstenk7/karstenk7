"""Populate current-season NFL team and player stats into PostgreSQL.

Team win/loss/points come from nfl_data_py's schedule data. Play-by-play
derived columns (yards_per_play, pass/rush EPA, third_down_pct,
turnover_margin) are left NULL for now — they require aggregating
nfl_data_py.import_pbp_data, which is a much larger download than is worth
forcing on every run of this script. The `nfl_team_stats` schema already
has room for them; a follow-up pass can backfill those columns once needed.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import nfl_data_py as nfl
import pandas as pd

from data_pipeline.config import get_settings
from data_pipeline.db.insert_games import get_connection

SEASON = "2024"

TEAM_STATS_SQL = """
INSERT INTO nfl_team_stats (
    team_abbr, game_date, season,
    wins, losses, ties, win_pct,
    points_per_game, points_allowed_per_game
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (team_abbr, game_date) DO UPDATE SET
    wins = EXCLUDED.wins,
    losses = EXCLUDED.losses,
    ties = EXCLUDED.ties,
    win_pct = EXCLUDED.win_pct,
    points_per_game = EXCLUDED.points_per_game,
    points_allowed_per_game = EXCLUDED.points_allowed_per_game
"""

PLAYER_STATS_SQL = """
INSERT INTO nfl_player_stats (
    player_name, team_abbr, position, game_date, season,
    passing_yards, passing_tds, rushing_yards, rushing_tds,
    receiving_yards, receiving_tds, receptions
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (player_name, game_date) DO UPDATE SET
    team_abbr = EXCLUDED.team_abbr,
    passing_yards = EXCLUDED.passing_yards,
    rushing_yards = EXCLUDED.rushing_yards,
    receiving_yards = EXCLUDED.receiving_yards
"""

_LEGACY_ABBR_MAP = {"STL": "LAR", "SD": "LAC", "OAK": "LV"}


def populate_team_stats(conn) -> int:
    print("Fetching NFL schedule for team win/loss/points aggregation...")
    schedule = nfl.import_schedules([int(SEASON)])
    schedule = schedule.dropna(subset=["home_score", "away_score"])

    home = schedule.rename(
        columns={"home_team": "team", "home_score": "points_for", "away_score": "points_against"}
    )[["team", "points_for", "points_against"]]
    away = schedule.rename(
        columns={"away_team": "team", "away_score": "points_for", "home_score": "points_against"}
    )[["team", "points_for", "points_against"]]
    games = pd.concat([home, away], ignore_index=True)
    games["team"] = games["team"].replace(_LEGACY_ABBR_MAP)

    today = date.today()
    records = []
    for team, grp in games.groupby("team"):
        wins = int((grp["points_for"] > grp["points_against"]).sum())
        losses = int((grp["points_for"] < grp["points_against"]).sum())
        ties = int((grp["points_for"] == grp["points_against"]).sum())
        played = len(grp)
        win_pct = (wins + 0.5 * ties) / played if played else None
        records.append((
            team, today, SEASON,
            wins, losses, ties, win_pct,
            float(grp["points_for"].mean()), float(grp["points_against"].mean()),
        ))

    with conn.cursor() as cur:
        cur.executemany(TEAM_STATS_SQL, records)
        conn.commit()

    print(f"Inserted {len(records)} team records")
    return len(records)


def populate_player_stats(conn) -> int:
    print("Fetching NFL weekly player stats...")
    weekly = nfl.import_weekly_data([int(SEASON)])
    today = date.today()

    agg = weekly.groupby(["player_display_name"]).agg(
        team_abbr=("recent_team", "last"),
        position=("position", "last"),
        passing_yards=("passing_yards", "sum"),
        passing_tds=("passing_tds", "sum"),
        rushing_yards=("rushing_yards", "sum"),
        rushing_tds=("rushing_tds", "sum"),
        receiving_yards=("receiving_yards", "sum"),
        receiving_tds=("receiving_tds", "sum"),
        receptions=("receptions", "sum"),
    ).reset_index()

    records = [
        (
            row["player_display_name"], row["team_abbr"], row["position"], today, SEASON,
            row["passing_yards"], row["passing_tds"], row["rushing_yards"], row["rushing_tds"],
            row["receiving_yards"], row["receiving_tds"], row["receptions"],
        )
        for _, row in agg.iterrows()
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
