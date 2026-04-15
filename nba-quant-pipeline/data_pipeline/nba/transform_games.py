"""Transform raw NBA API game logs into historical game rows."""

from __future__ import annotations

from typing import List, Tuple

import pandas as pd

DB_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "home_win",
    "actual_spread",
    "actual_total",
]

_REQUIRED_SOURCE_COLUMNS = {"GAME_ID", "MATCHUP", "GAME_DATE", "TEAM_ABBREVIATION", "PTS"}


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def transform_games(raw_games: pd.DataFrame, season: str) -> pd.DataFrame:
    """Convert team-level game logs into one row per game."""
    if raw_games.empty:
        return pd.DataFrame(columns=DB_COLUMNS)

    if not _REQUIRED_SOURCE_COLUMNS.issubset(raw_games.columns):
        missing = _REQUIRED_SOURCE_COLUMNS.difference(raw_games.columns)
        print(f"[ERROR] Missing expected columns for {season}: {sorted(missing)}")
        return pd.DataFrame(columns=DB_COLUMNS)

    valid_rows = raw_games.dropna(subset=["GAME_ID", "MATCHUP", "GAME_DATE", "TEAM_ABBREVIATION"])
    home_rows = valid_rows[valid_rows["MATCHUP"].astype(str).str.contains(" vs. ", na=False)].copy()
    away_rows = valid_rows[valid_rows["MATCHUP"].astype(str).str.contains(" @ ", na=False)].copy()

    if home_rows.empty or away_rows.empty:
        print(f"[ERROR] Could not build home/away splits for {season}.")
        return pd.DataFrame(columns=DB_COLUMNS)

    home_rows = home_rows.rename(
        columns={
            "TEAM_ABBREVIATION": "home_team",
            "PTS": "home_score",
            "GAME_DATE": "home_game_date",
        }
    )[["GAME_ID", "home_team", "home_score", "home_game_date"]]

    away_rows = away_rows.rename(
        columns={
            "TEAM_ABBREVIATION": "away_team",
            "PTS": "away_score",
            "GAME_DATE": "away_game_date",
        }
    )[["GAME_ID", "away_team", "away_score", "away_game_date"]]

    merged = home_rows.merge(away_rows, on="GAME_ID", how="inner")
    if merged.empty:
        return pd.DataFrame(columns=DB_COLUMNS)

    merged["home_score"] = _safe_numeric(merged["home_score"])
    merged["away_score"] = _safe_numeric(merged["away_score"])
    merged["game_date"] = pd.to_datetime(
        merged["home_game_date"].fillna(merged["away_game_date"]),
        errors="coerce",
    )

    cleaned = merged.dropna(
        subset=["GAME_ID", "home_team", "away_team", "home_score", "away_score", "game_date"]
    ).copy()

    if cleaned.empty:
        return pd.DataFrame(columns=DB_COLUMNS)

    cleaned["home_score"] = cleaned["home_score"].astype(int)
    cleaned["away_score"] = cleaned["away_score"].astype(int)
    cleaned["home_win"] = cleaned["home_score"] > cleaned["away_score"]
    cleaned["actual_spread"] = cleaned["home_score"] - cleaned["away_score"]
    cleaned["actual_total"] = cleaned["home_score"] + cleaned["away_score"]
    cleaned["season"] = season

    final = cleaned.rename(columns={"GAME_ID": "game_id"})[DB_COLUMNS]
    final = final.drop_duplicates(subset=["game_id"], keep="first").sort_values("game_date")
    final["game_date"] = pd.to_datetime(final["game_date"]).dt.date

    return final.reset_index(drop=True)


def to_records(games_df: pd.DataFrame) -> List[Tuple]:
    """Convert transformed games into tuple records for database insertion."""
    if games_df.empty:
        return []
    return [tuple(row) for row in games_df[DB_COLUMNS].itertuples(index=False, name=None)]
