"""Thin database access layer for the research pipeline.

All reads go through pandas.read_sql for convenience.
Write operations are intentionally excluded — research is read-only
against the production schema, and only writes to local files / new tables.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection

from research.config import ResearchConfig


def get_connection(cfg: Optional[ResearchConfig] = None) -> PgConnection:
    cfg = cfg or ResearchConfig()
    return psycopg2.connect(cfg.database_url)


@contextmanager
def connect(cfg: Optional[ResearchConfig] = None):
    conn = get_connection(cfg)
    try:
        yield conn
    finally:
        conn.close()


def read_sql(query: str, cfg: Optional[ResearchConfig] = None, **kwargs) -> pd.DataFrame:
    """Execute a SELECT and return a DataFrame."""
    with connect(cfg) as conn:
        return pd.read_sql(query, conn, **kwargs)
