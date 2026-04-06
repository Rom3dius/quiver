"""Data access for the teams table."""

from __future__ import annotations

import sqlite3

from quiver.db.models import Team


def get_all(conn: sqlite3.Connection) -> list[Team]:
    rows = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()
    return [Team.from_row(r) for r in rows]


def get_by_id(conn: sqlite3.Connection, team_id: int) -> Team | None:
    row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
    return Team.from_row(row) if row else None


def get_by_name(conn: sqlite3.Connection, name: str) -> Team | None:
    """Case-insensitive exact match on team name."""
    row = conn.execute(
        "SELECT * FROM teams WHERE LOWER(name) = LOWER(?)", (name,)
    ).fetchone()
    return Team.from_row(row) if row else None


def get_by_channel_id(conn: sqlite3.Connection, channel_id: str) -> Team | None:
    row = conn.execute(
        "SELECT * FROM teams WHERE discord_channel_id = ?", (channel_id,)
    ).fetchone()
    return Team.from_row(row) if row else None


def update_channel_id(
    conn: sqlite3.Connection, team_id: int, channel_id: str
) -> Team | None:
    conn.execute(
        "UPDATE teams SET discord_channel_id = ? WHERE id = ?",
        (channel_id, team_id),
    )
    conn.commit()
    return get_by_id(conn, team_id)
