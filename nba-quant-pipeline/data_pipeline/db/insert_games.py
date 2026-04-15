"""Database helpers for inserting historical games."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import psycopg2

from data_pipeline.config import Settings

InsertRecord = Tuple[str, str, object, str, str, int, int, bool, int, int]

INSERT_SQL = """
INSERT INTO historical_games (
    game_id,
    season,
    game_date,
    home_team,
    away_team,
    home_score,
    away_score,
    home_win,
    actual_spread,
    actual_total
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (game_id) DO NOTHING
"""


def get_connection(settings: Settings):
    """Open a psycopg2 connection from app settings."""
    if settings.database_url:
        return psycopg2.connect(settings.database_url)
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def _chunked(records: Sequence[InsertRecord], chunk_size: int) -> Iterable[Sequence[InsertRecord]]:
    for idx in range(0, len(records), chunk_size):
        yield records[idx : idx + chunk_size]


def insert_historical_games(
    conn,
    records: Sequence[InsertRecord],
    batch_size: int = 500,
    dry_run: bool = False,
) -> int:
    """
    Insert historical game records in batches.

    Returns number of rows reported inserted by PostgreSQL.
    """
    if not records:
        return 0

    if dry_run:
        print(f"[DRY RUN] Would insert {len(records)} rows into historical_games")
        return 0

    inserted_total = 0
    with conn.cursor() as cursor:
        for batch in _chunked(records, batch_size):
            cursor.executemany(INSERT_SQL, batch)
            inserted_total += max(cursor.rowcount, 0)
            conn.commit()
    return inserted_total
