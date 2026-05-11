"""Feature engineering for the NBA modeling pipeline.

All features are computed using ONLY pre-game information to avoid leakage.
The core pattern: for each game, compute rolling statistics from PRIOR games
for both the home and away team.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from research.config import ResearchConfig


def _rolling_team_stats(
    games: pd.DataFrame,
    team_col: str,
    windows: List[int],
) -> pd.DataFrame:
    """Compute rolling statistics for each team from their prior games.

    Args:
        games: historical_games sorted by game_date.
        team_col: "home" or "away" — determines perspective.
        windows: list of rolling window sizes.

    Returns one row per (game_id, team) with rolling features.
    """
    records = []

    # Build a per-team game log in chronological order
    # For each game, a team was either home or away
    team_logs = []
    for _, row in games.iterrows():
        team_logs.append({
            "game_id": row["game_id"],
            "game_date": row["game_date"],
            "team": row["home_team"],
            "role": "home",
            "pts_for": row["home_score"],
            "pts_against": row["away_score"],
            "won": row["home_win"],
            "spread": row["actual_spread"],
        })
        team_logs.append({
            "game_id": row["game_id"],
            "game_date": row["game_date"],
            "team": row["away_team"],
            "role": "away",
            "pts_for": row["away_score"],
            "pts_against": row["home_score"],
            "won": not row["home_win"],
            "spread": -row["actual_spread"],
        })

    tl = pd.DataFrame(team_logs).sort_values(["team", "game_date", "game_id"])

    for team, grp in tl.groupby("team"):
        grp = grp.sort_values("game_date").reset_index(drop=True)

        grp["pt_diff"] = grp["pts_for"] - grp["pts_against"]

        for w in windows:
            sfx = f"_{w}g"
            # .shift(1) ensures we only use games BEFORE the current one
            grp[f"roll_pts_for{sfx}"] = (
                grp["pts_for"].shift(1).rolling(w, min_periods=1).mean()
            )
            grp[f"roll_pts_against{sfx}"] = (
                grp["pts_against"].shift(1).rolling(w, min_periods=1).mean()
            )
            grp[f"roll_pt_diff{sfx}"] = (
                grp["pt_diff"].shift(1).rolling(w, min_periods=1).mean()
            )
            grp[f"roll_win_pct{sfx}"] = (
                grp["won"].astype(float).shift(1).rolling(w, min_periods=1).mean()
            )

        # Win/loss streak (positive = win streak, negative = loss streak)
        streaks = []
        current_streak = 0
        for i, row in grp.iterrows():
            streaks.append(current_streak)
            if row["won"]:
                current_streak = max(1, current_streak + 1)
            else:
                current_streak = min(-1, current_streak - 1)
        grp["streak"] = streaks

        # Rest days (days since last game)
        grp["prev_game_date"] = grp["game_date"].shift(1)
        grp["rest_days"] = (
            pd.to_datetime(grp["game_date"]) - pd.to_datetime(grp["prev_game_date"])
        ).dt.days
        grp["is_back_to_back"] = (grp["rest_days"] == 1).astype(int)

        # Games played in season so far (form indicator)
        grp["games_played"] = range(len(grp))

        records.append(grp)

    all_stats = pd.concat(records, ignore_index=True)
    return all_stats


def build_game_features(
    games: pd.DataFrame,
    cfg: Optional[ResearchConfig] = None,
) -> pd.DataFrame:
    """Build per-game features from historical games.

    For each game, attaches rolling stats for the home team and away team
    computed from their PRIOR games only.

    Returns a DataFrame with one row per game_id.
    """
    cfg = cfg or ResearchConfig()
    windows = cfg.rolling_windows

    games = games.copy()
    games["game_date"] = pd.to_datetime(games["game_date"])
    games = games.sort_values("game_date").reset_index(drop=True)

    team_stats = _rolling_team_stats(games, "both", windows)

    # Split into home-perspective and away-perspective
    home_stats = team_stats[team_stats["role"] == "home"].copy()
    away_stats = team_stats[team_stats["role"] == "away"].copy()

    # Build feature columns for home team
    rolling_cols = [c for c in home_stats.columns if c.startswith("roll_")]
    meta_cols = ["streak", "rest_days", "is_back_to_back", "games_played"]

    home_features = home_stats[["game_id"] + rolling_cols + meta_cols].copy()
    home_features = home_features.rename(
        columns={c: f"home_{c}" for c in rolling_cols + meta_cols}
    )

    away_features = away_stats[["game_id"] + rolling_cols + meta_cols].copy()
    away_features = away_features.rename(
        columns={c: f"away_{c}" for c in rolling_cols + meta_cols}
    )

    result = games[["game_id", "game_date", "season", "home_team", "away_team"]].merge(
        home_features, on="game_id", how="left"
    ).merge(
        away_features, on="game_id", how="left"
    )

    # Differential features (home minus away)
    for w in windows:
        sfx = f"_{w}g"
        result[f"diff_pts_for{sfx}"] = (
            result[f"home_roll_pts_for{sfx}"] - result[f"away_roll_pts_for{sfx}"]
        )
        result[f"diff_pts_against{sfx}"] = (
            result[f"home_roll_pts_against{sfx}"] - result[f"away_roll_pts_against{sfx}"]
        )
        result[f"diff_pt_diff{sfx}"] = (
            result[f"home_roll_pt_diff{sfx}"] - result[f"away_roll_pt_diff{sfx}"]
        )
        result[f"diff_win_pct{sfx}"] = (
            result[f"home_roll_win_pct{sfx}"] - result[f"away_roll_win_pct{sfx}"]
        )

    result["streak_diff"] = result["home_streak"] - result["away_streak"]
    result["rest_diff"] = result["home_rest_days"] - result["away_rest_days"]

    return result


def add_odds_features(
    game_features: pd.DataFrame,
    closing_lines: pd.DataFrame,
) -> pd.DataFrame:
    """Merge closing line odds features onto the game feature matrix.

    Adds:
        - closing_spread, closing_ml_home/away, implied_prob_home/away
        - closing_total
        - spread_bookmaker_count, spread_variance (consensus quality)
    """
    if closing_lines.empty:
        return game_features

    return game_features.merge(
        closing_lines,
        left_on="game_id",
        right_on="historical_game_id",
        how="left",
    ).drop(columns=["historical_game_id"], errors="ignore")


def add_line_movement_features(
    game_features: pd.DataFrame,
    line_movement: pd.DataFrame,
) -> pd.DataFrame:
    """Merge opening-to-closing line movement onto the feature matrix."""
    if line_movement.empty:
        return game_features

    return game_features.merge(
        line_movement,
        left_on="game_id",
        right_on="historical_game_id",
        how="left",
    ).drop(columns=["historical_game_id"], errors="ignore")
