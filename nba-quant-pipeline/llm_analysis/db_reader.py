"""
Read-only database access for the LLM analysis layer.

Connects to the same PostgreSQL database used by the existing pipeline.
All queries are SELECT-only — this module never writes data.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _get_connection():
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Run a read-only query and return rows as dicts."""
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_odds_for_team(
    team: str,
    hours: int = 24,
    market_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch recent odds snapshots for a team (home or away)."""
    since = datetime.utcnow() - timedelta(hours=hours)
    sql = """
        SELECT id, game_id, commence_time, home_team, away_team,
               bookmaker, market_type, outcome_name, price, point,
               captured_at
        FROM odds_snapshots
        WHERE (home_team = %s OR away_team = %s)
          AND captured_at >= %s
    """
    params: list = [team, team, since]
    if market_type:
        sql += " AND market_type = %s"
        params.append(market_type)
    sql += " ORDER BY captured_at ASC"
    return query(sql, tuple(params))


def get_team_stats(team_name: str) -> List[Dict[str, Any]]:
    """Fetch the most recent team stats snapshot."""
    return query(
        "SELECT * FROM team_stats WHERE team_name = %s ORDER BY game_date DESC LIMIT 1",
        (team_name,),
    )


def get_historical_games(
    team: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Fetch recent historical games involving a team."""
    return query(
        """
        SELECT * FROM historical_games
        WHERE home_team = %s OR away_team = %s
        ORDER BY game_date DESC
        LIMIT %s
        """,
        (team, team, limit),
    )


def get_all_recent_odds(hours: int = 24) -> List[Dict[str, Any]]:
    """Fetch all odds snapshots captured in the last N hours."""
    since = datetime.utcnow() - timedelta(hours=hours)
    return query(
        """
        SELECT id, game_id, commence_time, home_team, away_team,
               bookmaker, market_type, outcome_name, price, point,
               captured_at
        FROM odds_snapshots
        WHERE captured_at >= %s
        ORDER BY captured_at ASC
        """,
        (since,),
    )


def get_teams() -> List[Dict[str, Any]]:
    """Return all team records."""
    return query("SELECT abbreviation, full_name, city, conference FROM teams ORDER BY abbreviation")


def resolve_team_abbreviation(user_input: str) -> Optional[str]:
    """
    Best-effort resolution of a user-provided team name to its abbreviation.
    Checks abbreviation, full_name, and city (case-insensitive).
    """
    user_input_lower = user_input.strip().lower()
    teams = get_teams()
    for t in teams:
        if user_input_lower == t["abbreviation"].lower():
            return t["abbreviation"]
    for t in teams:
        if user_input_lower in t["full_name"].lower():
            return t["abbreviation"]
    for t in teams:
        if user_input_lower in t["city"].lower():
            return t["abbreviation"]
    return None
