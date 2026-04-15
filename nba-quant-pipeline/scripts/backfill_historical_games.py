"""Backfill historical NBA games into PostgreSQL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - optional dependency
    tqdm = None

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_pipeline.config import get_settings
from data_pipeline.db.insert_games import get_connection, insert_historical_games
from data_pipeline.nba.fetch_games import fetch_season_games
from data_pipeline.nba.transform_games import to_records, transform_games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill historical NBA game outcomes into historical_games table."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and transform data without inserting into PostgreSQL.",
    )
    return parser.parse_args()


def run_backfill(dry_run: bool = False) -> None:
    settings = get_settings()
    seasons = settings.seasons
    season_iterable = tqdm(seasons, desc="Backfilling seasons") if tqdm else seasons

    conn = None
    if not dry_run:
        conn = get_connection(settings)

    inserted_total = 0
    processed_total = 0

    try:
        for season in season_iterable:
            print(f"\n[INFO] Processing season: {season}")
            try:
                raw_games = fetch_season_games(
                    season=season,
                    max_retries=settings.max_retries,
                    base_backoff_seconds=settings.base_backoff_seconds,
                    rate_limit_seconds=settings.rate_limit_seconds,
                )
                print(f"[INFO] Fetched {len(raw_games)} team-game rows for {season}")

                transformed = transform_games(raw_games, season)
                print(f"[INFO] Built {len(transformed)} unique games for {season}")

                records = to_records(transformed)
                if dry_run:
                    print(f"[DRY RUN] {season}: prepared {len(records)} rows")
                    continue

                inserted = insert_historical_games(
                    conn=conn,
                    records=records,
                    batch_size=settings.batch_size,
                    dry_run=dry_run,
                )
                inserted_total += inserted
                processed_total += len(records)
                print(f"[INFO] Inserted {inserted} rows for {season}")
            except Exception as exc:
                print(f"[ERROR] Season {season} failed: {exc}")
                continue
    finally:
        if conn is not None:
            conn.close()

    if dry_run:
        print("\n[INFO] Dry run complete.")
    else:
        print(
            "\n[INFO] Backfill complete. "
            f"Processed rows: {processed_total}. Inserted rows: {inserted_total}."
        )


if __name__ == "__main__":
    args = parse_args()
    run_backfill(dry_run=args.dry_run)
