"""Configuration for the NBA historical backfill pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SEASONS: List[str] = [
    "2015-16",
    "2016-17",
    "2017-18",
    "2018-19",
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
]


@dataclass(frozen=True)
class Settings:
    """Runtime settings for backfilling historical NBA games."""

    database_url: Optional[str]
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    seasons: List[str]
    batch_size: int
    max_retries: int
    base_backoff_seconds: float
    rate_limit_seconds: float


def _parse_seasons(raw_seasons: Optional[str]) -> List[str]:
    if not raw_seasons:
        return DEFAULT_SEASONS
    seasons = [season.strip() for season in raw_seasons.split(",") if season.strip()]
    return seasons or DEFAULT_SEASONS


def get_settings() -> Settings:
    """Load settings from environment variables."""
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "postgres"),
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=os.getenv("DB_PASSWORD", ""),
        seasons=_parse_seasons(os.getenv("BACKFILL_SEASONS")),
        batch_size=int(os.getenv("BACKFILL_BATCH_SIZE", "500")),
        max_retries=int(os.getenv("BACKFILL_MAX_RETRIES", "5")),
        base_backoff_seconds=float(os.getenv("BACKFILL_BASE_BACKOFF", "1.0")),
        rate_limit_seconds=float(os.getenv("BACKFILL_RATE_LIMIT_SECONDS", "1.0")),
    )
