"""SQLite connection factory with WAL mode and safety pragmas."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    """Create a SQLite connection configured for concurrent access.

    Enables WAL mode, foreign keys, and a 5-second busy timeout.
    Returns rows as sqlite3.Row for dict-like access.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # WAL (Write-Ahead Logging) allows concurrent reads while the bot and
    # Flask are writing — without WAL, readers block writers and vice-versa.
    conn.execute("PRAGMA journal_mode = WAL")
    # Wait up to 5 s when another connection holds the write lock, rather
    # than failing immediately with SQLITE_BUSY.
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    # NORMAL sync is safe with WAL — it skips fsync on the WAL file for
    # each transaction, trading a small durability window for ~2x speed.
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn
