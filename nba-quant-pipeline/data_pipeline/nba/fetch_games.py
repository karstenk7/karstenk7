"""Fetch historical NBA games from nba_api."""

from __future__ import annotations

import time

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog


def fetch_season_games(
    season: str,
    max_retries: int = 5,
    base_backoff_seconds: float = 1.0,
    rate_limit_seconds: float = 1.0,
) -> pd.DataFrame:
    """
    Fetch a full season game log from the NBA Stats API.

    Raises an exception only after exhausting all retries.
    """
    for attempt in range(1, max_retries + 1):
        try:
            game_log = leaguegamelog.LeagueGameLog(
                season=season,
                player_or_team_abbreviation="T",
                season_type_all_star="Regular Season",
            )
            data = game_log.get_data_frames()[0]
            return data
        except Exception as exc:
            print(
                f"[ERROR] Failed to fetch {season} "
                f"(attempt {attempt}/{max_retries}): {exc}"
            )
            if attempt == max_retries:
                raise
            sleep_seconds = base_backoff_seconds * (2 ** (attempt - 1))
            print(f"[INFO] Retrying {season} in {sleep_seconds:.1f}s...")
            time.sleep(sleep_seconds)
        finally:
            # Respect API rate limits regardless of success or failure.
            time.sleep(rate_limit_seconds)

    return pd.DataFrame()
