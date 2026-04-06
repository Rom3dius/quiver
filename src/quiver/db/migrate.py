"""Apply database schema and optional seed data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SQL_DIR = Path(__file__).parent


def apply_schema(conn: sqlite3.Connection) -> None:
    """Execute schema.sql to create all tables idempotently."""
    schema_sql = (_SQL_DIR / "schema.sql").read_text()
    conn.executescript(schema_sql)


def apply_seed(conn: sqlite3.Connection) -> None:
    """Insert seed data (17 teams) idempotently via INSERT OR IGNORE."""
    seed_sql = (_SQL_DIR / "seed.sql").read_text()
    conn.executescript(seed_sql)


def init_db(conn: sqlite3.Connection) -> None:
    """Apply schema and seed data."""
    apply_schema(conn)
    apply_seed(conn)
