"""Transform raw nfl_data_py schedules into historical game rows."""

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
    "league",
]

_REQUIRED_SOURCE_COLUMNS = {
    "game_id",
    "gameday",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
}

# nfl_data_py schedules use the franchise's abbreviation at the time of the
# game. Our `teams` table only seeds current-era abbreviations, so relocated
# franchises need normalizing before the historical_games FK is checked.
_LEGACY_ABBR_MAP = {
    "STL": "LAR",  # St. Louis Rams -> Los Angeles Rams (2016)
    "SD": "LAC",  # San Diego Chargers -> Los Angeles Chargers (2017)
    "OAK": "LV",  # Oakland Raiders -> Las Vegas Raiders (2020)
}


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_abbr(series: pd.Series) -> pd.Series:
    return series.replace(_LEGACY_ABBR_MAP)


def transform_games(raw_games: pd.DataFrame, season: str) -> pd.DataFrame:
    """Convert an nfl_data_py schedule into one row per completed game."""
    if raw_games.empty:
        return pd.DataFrame(columns=DB_COLUMNS)

    if not _REQUIRED_SOURCE_COLUMNS.issubset(raw_games.columns):
        missing = _REQUIRED_SOURCE_COLUMNS.difference(raw_games.columns)
        print(f"[ERROR] Missing expected columns for {season}: {sorted(missing)}")
        return pd.DataFrame(columns=DB_COLUMNS)

    games = raw_games.dropna(subset=["game_id", "home_team", "away_team"]).copy()
    games["home_team"] = _normalize_abbr(games["home_team"])
    games["away_team"] = _normalize_abbr(games["away_team"])
    games["home_score"] = _safe_numeric(games["home_score"])
    games["away_score"] = _safe_numeric(games["away_score"])
    games["game_date"] = pd.to_datetime(games["gameday"], errors="coerce")

    # Only completed games carry final scores; future/bye entries drop out here.
    completed = games.dropna(subset=["home_score", "away_score", "game_date"]).copy()
    if completed.empty:
        return pd.DataFrame(columns=DB_COLUMNS)

    completed["home_score"] = completed["home_score"].astype(int)
    completed["away_score"] = completed["away_score"].astype(int)
    completed["home_win"] = completed["home_score"] > completed["away_score"]
    completed["actual_spread"] = completed["home_score"] - completed["away_score"]
    completed["actual_total"] = completed["home_score"] + completed["away_score"]
    completed["season"] = season
    completed["league"] = "nfl"

    final = completed[DB_COLUMNS]
    final = final.drop_duplicates(subset=["game_id"], keep="first").sort_values("game_date")
    final["game_date"] = pd.to_datetime(final["game_date"]).dt.date

    return final.reset_index(drop=True)


def to_records(games_df: pd.DataFrame) -> List[Tuple]:
    """Convert transformed games into tuple records for database insertion."""
    if games_df.empty:
        return []
    return [tuple(row) for row in games_df[DB_COLUMNS].itertuples(index=False, name=None)]
