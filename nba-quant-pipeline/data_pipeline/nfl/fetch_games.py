"""Fetch historical NFL games from nfl_data_py."""

from __future__ import annotations

import time

import nfl_data_py as nfl
import pandas as pd


def fetch_season_games(
    season: str,
    max_retries: int = 5,
    base_backoff_seconds: float = 1.0,
    rate_limit_seconds: float = 1.0,
) -> pd.DataFrame:
    """
    Fetch a full season schedule (including final scores) from nfl_data_py.

    Raises an exception only after exhausting all retries.
    """
    season_year = int(season)
    for attempt in range(1, max_retries + 1):
        try:
            data = nfl.import_schedules([season_year])
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
