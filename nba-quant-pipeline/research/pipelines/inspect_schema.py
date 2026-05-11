"""Programmatic schema inspection.

Run against the live database to produce a complete audit:
    python -m research.pipelines.inspect_schema

Produces research/outputs/schema_inspection.txt with:
- all tables, columns, types
- primary keys, foreign keys, indexes
- row counts
- sample data
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.config import ResearchConfig
from research.db import connect


def inspect(cfg: ResearchConfig | None = None) -> str:
    cfg = cfg or ResearchConfig()
    lines: list[str] = []

    with connect(cfg) as conn:
        cur = conn.cursor()

        # Tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]

        lines.append("=" * 70)
        lines.append("LIVE SCHEMA INSPECTION")
        lines.append("=" * 70)

        for table in tables:
            lines.append(f"\n{'─' * 50}")
            lines.append(f"TABLE: {table}")
            lines.append(f"{'─' * 50}")

            # Row count
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            lines.append(f"  Rows: {count:,}")

            # Columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable,
                       column_default, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table,))
            cols = cur.fetchall()
            lines.append("  Columns:")
            for name, dtype, nullable, default, max_len in cols:
                size = f"({max_len})" if max_len else ""
                null = "NULL" if nullable == "YES" else "NOT NULL"
                dflt = f" DEFAULT {default}" if default else ""
                lines.append(f"    {name:<30s} {dtype}{size:<20s} {null}{dflt}")

            # Primary key
            cur.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass AND i.indisprimary
            """, (table,))
            pk_cols = [r[0] for r in cur.fetchall()]
            if pk_cols:
                lines.append(f"  PK: ({', '.join(pk_cols)})")

            # Foreign keys
            cur.execute("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_name = %s
                  AND tc.constraint_type = 'FOREIGN KEY'
            """, (table,))
            fks = cur.fetchall()
            if fks:
                lines.append("  Foreign Keys:")
                for col, ftable, fcol in fks:
                    lines.append(f"    {col} → {ftable}({fcol})")

            # Indexes
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = %s AND schemaname = 'public'
            """, (table,))
            idxs = cur.fetchall()
            if idxs:
                lines.append("  Indexes:")
                for idx_name, idx_def in idxs:
                    lines.append(f"    {idx_name}")

            # Date range (if applicable)
            date_cols = [c[0] for c in cols if "date" in c[0] or "time" in c[0] or c[0] == "captured_at"]
            for dc in date_cols[:1]:
                try:
                    cur.execute(f"SELECT MIN({dc}), MAX({dc}) FROM {table}")
                    mn, mx = cur.fetchone()
                    if mn:
                        lines.append(f"  Date range ({dc}): {mn} → {mx}")
                except Exception:
                    pass

    report = "\n".join(lines)

    out = cfg.output_dir / "schema_inspection.txt"
    out.write_text(report)
    print(report)
    print(f"\nSaved to {out}")
    return report


if __name__ == "__main__":
    inspect()
