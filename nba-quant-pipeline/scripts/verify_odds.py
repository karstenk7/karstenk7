"""Quick verification of odds_snapshots data quality."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_pipeline.config import get_settings
from data_pipeline.db.insert_games import get_connection


def run_checks() -> None:
    settings = get_settings()
    conn = get_connection(settings)
    cur = conn.cursor()

    print("=== Odds Snapshot Verification ===\n")

    cur.execute("SELECT COUNT(*) FROM odds_snapshots")
    total = cur.fetchone()[0]
    print(f"Total rows: {total}")

    if total == 0:
        print("No data yet — run the scraper first.")
        conn.close()
        return

    cur.execute(
        "SELECT sport, COUNT(*) FROM odds_snapshots GROUP BY sport ORDER BY sport"
    )
    print("\nRows by sport:")
    for sport, cnt in cur.fetchall():
        print(f"  {sport}: {cnt}")

    cur.execute(
        "SELECT market_type, COUNT(*) FROM odds_snapshots "
        "GROUP BY market_type ORDER BY market_type"
    )
    print("\nRows by market type:")
    for mtype, cnt in cur.fetchall():
        print(f"  {mtype}: {cnt}")

    cur.execute(
        "SELECT bookmaker, COUNT(*) FROM odds_snapshots "
        "GROUP BY bookmaker ORDER BY COUNT(*) DESC LIMIT 10"
    )
    print("\nTop bookmakers:")
    for bk, cnt in cur.fetchall():
        print(f"  {bk}: {cnt}")

    cur.execute(
        "SELECT COUNT(DISTINCT game_id) FROM odds_snapshots"
    )
    print(f"\nDistinct API game IDs: {cur.fetchone()[0]}")

    cur.execute(
        "SELECT COUNT(DISTINCT historical_game_id) FROM odds_snapshots "
        "WHERE historical_game_id IS NOT NULL"
    )
    print(f"Mapped to historical games: {cur.fetchone()[0]}")

    cur.execute(
        "SELECT COUNT(*) FROM odds_snapshots WHERE historical_game_id IS NULL"
    )
    print(f"Unmapped rows (expected for upcoming games): {cur.fetchone()[0]}")

    cur.execute(
        "SELECT MIN(captured_at), MAX(captured_at) FROM odds_snapshots"
    )
    first, last = cur.fetchone()
    print(f"\nCapture window: {first} → {last}")

    cur.execute(
        "SELECT captured_at, COUNT(*) FROM odds_snapshots "
        "GROUP BY captured_at ORDER BY captured_at DESC LIMIT 5"
    )
    print("\nRecent batch sizes (last 5 scrapes):")
    for ts, cnt in cur.fetchall():
        print(f"  {ts}: {cnt} rows")

    cur.execute(
        "SELECT COUNT(*) FROM pipeline_runs "
        "WHERE job_name LIKE 'odds_scraper_%'"
    )
    runs = cur.fetchone()[0]
    print(f"\nPipeline runs recorded: {runs}")

    if runs > 0:
        cur.execute(
            "SELECT job_name, status, rows_in, rows_out, started_at, "
            "ended_at - started_at AS duration "
            "FROM pipeline_runs WHERE job_name LIKE 'odds_scraper_%' "
            "ORDER BY started_at DESC LIMIT 5"
        )
        print("Recent runs:")
        for row in cur.fetchall():
            print(f"  {row[0]} | {row[1]} | in={row[2]} out={row[3]} | {row[4]} ({row[5]})")

    conn.close()
    print("\n=== Done ===")


if __name__ == "__main__":
    run_checks()
