"""Build the canonical modeling dataset.

This is the main entry point that combines:
1. Historical game outcomes (targets)
2. Closing line extraction (odds features)
3. Rolling team performance features
4. Line movement features

Into ONE clean DataFrame with one row per game.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from research.config import ResearchConfig
from research.db import read_sql
from research.features.engineering import (
    add_line_movement_features,
    add_odds_features,
    build_game_features,
)
from research.sql.closing_lines import (
    build_closing_lines,
    build_line_movement,
)
from research.sql.queries import HISTORICAL_GAMES

logger = logging.getLogger(__name__)


def load_historical_games(cfg: Optional[ResearchConfig] = None) -> pd.DataFrame:
    return read_sql(HISTORICAL_GAMES, cfg)


def build_targets(games: pd.DataFrame) -> pd.DataFrame:
    """Create clean modeling targets from historical games."""
    targets = games[["game_id"]].copy()
    targets["home_win"] = games["home_win"].astype(int)
    targets["margin"] = games["actual_spread"]  # home_score - away_score
    targets["total_points"] = games["actual_total"]
    return targets


def build_modeling_dataset(
    cfg: Optional[ResearchConfig] = None,
    include_odds: bool = True,
    save: bool = True,
) -> pd.DataFrame:
    """Build the full modeling dataset.

    Args:
        cfg: Research configuration.
        include_odds: If True, attempt to load and merge odds data.
            Set to False if odds_snapshots is empty or unavailable.
        save: If True, save the dataset to parquet.

    Returns:
        DataFrame with one row per game, containing targets + features.
    """
    cfg = cfg or ResearchConfig()

    # Step 1: Load historical games
    logger.info("Loading historical games...")
    games = load_historical_games(cfg)
    logger.info(f"Loaded {len(games)} historical games")

    if games.empty:
        logger.warning("No historical games found")
        return pd.DataFrame()

    # Step 2: Build targets
    logger.info("Building targets...")
    targets = build_targets(games)

    # Step 3: Build rolling features from game history
    logger.info("Building rolling features...")
    features = build_game_features(games, cfg)
    logger.info(f"Built {len(features.columns)} feature columns")

    # Step 4: Merge targets
    dataset = features.merge(targets, on="game_id", how="left")

    # Step 5: Closing lines (odds features)
    if include_odds:
        logger.info("Building closing lines...")
        try:
            closing = build_closing_lines(cfg)
            if not closing.empty:
                dataset = add_odds_features(dataset, closing)
                logger.info(f"Merged closing lines for {len(closing)} games")

                # Add spread cover target (requires closing spread)
                if "closing_spread" in dataset.columns:
                    dataset["did_home_cover"] = (
                        dataset["margin"] + dataset["closing_spread"] > 0
                    ).astype(float)
                    # Push = NaN
                    push_mask = (dataset["margin"] + dataset["closing_spread"]) == 0
                    dataset.loc[push_mask, "did_home_cover"] = float("nan")

                    # Over/under target
                    if "closing_total" in dataset.columns:
                        dataset["went_over"] = (
                            dataset["total_points"] > dataset["closing_total"]
                        ).astype(float)
                        push_mask = dataset["total_points"] == dataset["closing_total"]
                        dataset.loc[push_mask, "went_over"] = float("nan")
            else:
                logger.info("No closing lines available — odds features skipped")
        except Exception as e:
            logger.warning(f"Could not load odds data: {e}")
            logger.info("Proceeding without odds features")

    # Step 6: Line movement
    if include_odds:
        try:
            movement = build_line_movement(cfg)
            if not movement.empty:
                dataset = add_line_movement_features(dataset, movement)
                logger.info("Added line movement features")
        except Exception as e:
            logger.warning(f"Could not compute line movement: {e}")

    # Step 7: Sort and set index
    dataset = dataset.sort_values("game_date").reset_index(drop=True)

    # Step 8: Save
    if save:
        out_path = cfg.output_dir / "modeling_dataset.parquet"
        dataset.to_parquet(out_path, index=False)
        logger.info(f"Saved modeling dataset to {out_path}")

        # Also save a diagnostic summary
        _save_summary(dataset, cfg)

    return dataset


def _save_summary(df: pd.DataFrame, cfg: ResearchConfig) -> None:
    """Write a quick summary of the dataset."""
    summary_path = cfg.output_dir / "dataset_summary.txt"
    lines = [
        "=== Modeling Dataset Summary ===",
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
        f"Seasons: {sorted(df['season'].unique()) if 'season' in df.columns else 'N/A'}",
        f"Date range: {df['game_date'].min()} to {df['game_date'].max()}",
        "",
        "--- Column list ---",
    ]
    for col in df.columns:
        null_pct = df[col].isna().mean() * 100
        lines.append(f"  {col:<40s} dtype={str(df[col].dtype):<12s} null={null_pct:.1f}%")

    lines.append("")
    lines.append("--- Target distributions ---")
    if "home_win" in df.columns:
        lines.append(f"  home_win mean: {df['home_win'].mean():.3f}")
    if "margin" in df.columns:
        lines.append(f"  margin mean: {df['margin'].mean():.2f}, std: {df['margin'].std():.2f}")
    if "did_home_cover" in df.columns:
        lines.append(f"  did_home_cover mean: {df['did_home_cover'].mean():.3f} (excl push)")

    summary_path.write_text("\n".join(lines))
    logger.info(f"Saved dataset summary to {summary_path}")


def get_train_test_split(
    dataset: pd.DataFrame,
    cfg: Optional[ResearchConfig] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset by season for temporal train/test split.

    Everything before test_season_start is train, the rest is test.
    """
    cfg = cfg or ResearchConfig()
    train = dataset[dataset["season"] < cfg.test_season_start].copy()
    test = dataset[dataset["season"] >= cfg.test_season_start].copy()
    return train, test
