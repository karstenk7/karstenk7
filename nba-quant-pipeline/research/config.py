"""Research pipeline configuration.

Reuses the project-level .env for DATABASE_URL and adds
research-specific settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SEASONS_BY_LEAGUE: Dict[str, List[str]] = {
    "nba": [
        "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
        "2020-21", "2021-22", "2022-23", "2023-24",
    ],
    "nfl": [
        "2015", "2016", "2017", "2018", "2019",
        "2020", "2021", "2022", "2023", "2024",
    ],
}

TEST_SEASON_START_BY_LEAGUE: Dict[str, str] = {
    "nba": "2023-24",
    "nfl": "2024",
}


@dataclass(frozen=True)
class ResearchConfig:
    database_url: str = field(
        default_factory=lambda: os.environ["DATABASE_URL"]
    )

    # 'nba' or 'nfl' — selects the default seasons/test split below unless
    # overridden explicitly.
    league: str = field(default_factory=lambda: os.getenv("LEAGUE", "nba").lower())

    # Historical seasons available in the DB. Defaults to the full list for
    # `league` (set in __post_init__) when not passed explicitly.
    seasons: Optional[List[str]] = None

    # Rolling window sizes for feature engineering (in games)
    rolling_windows: List[int] = field(default_factory=lambda: [5, 10, 20])

    # Train/test split: seasons before this are train, this and after are test.
    # Defaults to the last season for `league` when not passed explicitly.
    test_season_start: Optional[str] = None

    # Minimum odds snapshots to consider a closing line valid
    min_snapshots_for_closing: int = 1

    # Output paths
    output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "research" / "outputs"
    )

    def __post_init__(self):
        if self.seasons is None:
            object.__setattr__(
                self, "seasons", SEASONS_BY_LEAGUE.get(self.league, SEASONS_BY_LEAGUE["nba"])
            )
        if self.test_season_start is None:
            object.__setattr__(
                self,
                "test_season_start",
                TEST_SEASON_START_BY_LEAGUE.get(self.league, TEST_SEASON_START_BY_LEAGUE["nba"]),
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)
