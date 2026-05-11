"""Research pipeline configuration.

Reuses the project-level .env for DATABASE_URL and adds
research-specific settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class ResearchConfig:
    database_url: str = field(
        default_factory=lambda: os.environ["DATABASE_URL"]
    )

    # Historical seasons available in the DB
    seasons: List[str] = field(default_factory=lambda: [
        "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
        "2020-21", "2021-22", "2022-23", "2023-24",
    ])

    # Rolling window sizes for feature engineering (in games)
    rolling_windows: List[int] = field(default_factory=lambda: [5, 10, 20])

    # Train/test split: seasons before this are train, this and after are test
    test_season_start: str = "2023-24"

    # Minimum odds snapshots to consider a closing line valid
    min_snapshots_for_closing: int = 1

    # Output paths
    output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "research" / "outputs"
    )

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
