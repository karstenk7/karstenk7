"""Configuration for historical backfill pipelines (NBA and NFL)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

SEASONS_BY_LEAGUE: Dict[str, List[str]] = {
    "nba": [
        "2015-16",
        "2016-17",
        "2017-18",
        "2018-19",
        "2019-20",
        "2020-21",
        "2021-22",
        "2022-23",
        "2023-24",
    ],
    "nfl": [
        "2015",
        "2016",
        "2017",
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
    ],
}

# Backward-compatible alias for existing NBA-only call sites.
DEFAULT_SEASONS: List[str] = SEASONS_BY_LEAGUE["nba"]


@dataclass(frozen=True)
class Settings:
    """Runtime settings for backfilling historical games."""

    database_url: Optional[str]
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    league: str
    seasons: List[str]
    batch_size: int
    max_retries: int
    base_backoff_seconds: float
    rate_limit_seconds: float


def _parse_seasons(raw_seasons: Optional[str], league: str) -> List[str]:
    default = SEASONS_BY_LEAGUE.get(league, DEFAULT_SEASONS)
    if not raw_seasons:
        return default
    seasons = [season.strip() for season in raw_seasons.split(",") if season.strip()]
    return seasons or default


def get_settings() -> Settings:
    """Load settings from environment variables."""
    league = os.getenv("LEAGUE", "nba").lower()
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "postgres"),
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=os.getenv("DB_PASSWORD", ""),
        league=league,
        seasons=_parse_seasons(os.getenv("BACKFILL_SEASONS"), league),
        batch_size=int(os.getenv("BACKFILL_BATCH_SIZE", "500")),
        max_retries=int(os.getenv("BACKFILL_MAX_RETRIES", "5")),
        base_backoff_seconds=float(os.getenv("BACKFILL_BASE_BACKOFF", "1.0")),
        rate_limit_seconds=float(os.getenv("BACKFILL_RATE_LIMIT_SECONDS", "1.0")),
    )
