"""Closing line extraction and pivoting.

Transforms raw per-bookmaker, per-outcome odds rows into one row per game
with consensus closing spread, moneyline, and total.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from research.config import ResearchConfig
from research.db import read_sql
from research.sql.queries import CLOSING_LINES, OPENING_LINES


def american_to_implied_prob(price: float) -> float:
    """Convert American odds to implied probability (no vig removal)."""
    if price >= 100:
        return 100.0 / (price + 100.0)
    else:
        return (-price) / (-price + 100.0)


def _load_closing_lines(cfg: Optional[ResearchConfig] = None) -> pd.DataFrame:
    return read_sql(CLOSING_LINES, cfg)


def _load_opening_lines(cfg: Optional[ResearchConfig] = None) -> pd.DataFrame:
    return read_sql(OPENING_LINES, cfg)


def _pivot_market(
    df: pd.DataFrame,
    market: str,
    home_team_col: str = "home_team",
) -> pd.DataFrame:
    """Pivot a single market type into per-game columns.

    For spreads:  closing_spread (home), closing_spread_price
    For h2h:      closing_ml_home, closing_ml_away, implied_prob_home
    For totals:   closing_total, closing_over_price, closing_under_price
    """
    mkt = df[df["market_type"] == market].copy()
    if mkt.empty:
        return pd.DataFrame(columns=["historical_game_id"])

    if market == "spreads":
        home_spreads = mkt[mkt["outcome_name"] == mkt[home_team_col]].copy()
        agg = (
            home_spreads.groupby("historical_game_id")
            .agg(
                closing_spread=("point", "median"),
                closing_spread_price=("price", "median"),
                spread_bookmaker_count=("bookmaker", "nunique"),
                spread_variance=("point", "var"),
            )
            .reset_index()
        )
        agg["spread_variance"] = agg["spread_variance"].fillna(0)
        return agg

    elif market == "h2h":
        home_ml = mkt[mkt["outcome_name"] == mkt[home_team_col]].copy()
        away_ml = mkt[mkt["outcome_name"] != mkt[home_team_col]].copy()

        home_agg = (
            home_ml.groupby("historical_game_id")
            .agg(closing_ml_home=("price", "median"))
            .reset_index()
        )
        away_agg = (
            away_ml.groupby("historical_game_id")
            .agg(closing_ml_away=("price", "median"))
            .reset_index()
        )
        merged = home_agg.merge(away_agg, on="historical_game_id", how="outer")
        merged["implied_prob_home"] = merged["closing_ml_home"].apply(
            lambda x: american_to_implied_prob(x) if pd.notna(x) else np.nan
        )
        merged["implied_prob_away"] = merged["closing_ml_away"].apply(
            lambda x: american_to_implied_prob(x) if pd.notna(x) else np.nan
        )
        return merged

    elif market == "totals":
        over = mkt[mkt["outcome_name"].str.lower() == "over"].copy()
        under = mkt[mkt["outcome_name"].str.lower() == "under"].copy()

        over_agg = (
            over.groupby("historical_game_id")
            .agg(
                closing_total=("point", "median"),
                closing_over_price=("price", "median"),
            )
            .reset_index()
        )
        under_agg = (
            under.groupby("historical_game_id")
            .agg(closing_under_price=("price", "median"))
            .reset_index()
        )
        return over_agg.merge(under_agg, on="historical_game_id", how="outer")

    return pd.DataFrame(columns=["historical_game_id"])


def build_closing_lines(cfg: Optional[ResearchConfig] = None) -> pd.DataFrame:
    """Build one row per game with consensus closing lines across all markets.

    Returns columns:
        historical_game_id, closing_spread, closing_spread_price,
        spread_bookmaker_count, spread_variance,
        closing_ml_home, closing_ml_away,
        implied_prob_home, implied_prob_away,
        closing_total, closing_over_price, closing_under_price
    """
    raw = _load_closing_lines(cfg)
    if raw.empty:
        return pd.DataFrame()

    spreads = _pivot_market(raw, "spreads")
    h2h = _pivot_market(raw, "h2h")
    totals = _pivot_market(raw, "totals")

    result = spreads
    for right in [h2h, totals]:
        if not right.empty:
            result = result.merge(right, on="historical_game_id", how="outer")

    return result


def build_opening_lines(cfg: Optional[ResearchConfig] = None) -> pd.DataFrame:
    """Build opening lines (first captured snapshot per game) for line movement."""
    raw = _load_opening_lines(cfg)
    if raw.empty:
        return pd.DataFrame()

    # For opening lines, pivot spreads only (most useful for movement)
    spreads = raw[raw["market_type"] == "spreads"].copy()
    if spreads.empty:
        return pd.DataFrame(columns=["historical_game_id"])

    # We don't have home_team in opening lines query — join back if needed
    # For now, take median of all spread points per game as opening spread
    agg = (
        spreads.groupby("historical_game_id")
        .agg(
            opening_spread=("open_point", "median"),
            opening_spread_price=("open_price", "median"),
        )
        .reset_index()
    )
    return agg


def build_line_movement(cfg: Optional[ResearchConfig] = None) -> pd.DataFrame:
    """Compute opening-to-closing line movement per game."""
    closing = build_closing_lines(cfg)
    opening = build_opening_lines(cfg)

    if closing.empty or opening.empty:
        return pd.DataFrame()

    merged = closing.merge(opening, on="historical_game_id", how="inner")
    merged["spread_movement"] = merged["closing_spread"] - merged["opening_spread"]
    return merged[["historical_game_id", "opening_spread", "closing_spread", "spread_movement"]]
