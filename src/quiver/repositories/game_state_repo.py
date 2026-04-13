"""Data access for the game_state table."""

from __future__ import annotations

import sqlite3

from quiver.db.models import GameState


def get(conn: sqlite3.Connection) -> GameState | None:
    """Return the singleton game state row, or None if missing."""
    row = conn.execute("SELECT * FROM game_state WHERE id = 1").fetchone()
    return GameState.from_row(row) if row else None


def start(conn: sqlite3.Connection) -> GameState:
    """Start the game clock. Clears any previous ended_at."""
    conn.execute(
        """UPDATE game_state
           SET started_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
               ended_at = NULL
           WHERE id = 1""",
    )
    conn.commit()
    return get(conn)


def stop(conn: sqlite3.Connection) -> GameState:
    """Stop the game clock."""
    conn.execute(
        """UPDATE game_state
           SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE id = 1""",
    )
    conn.commit()
    return get(conn)
