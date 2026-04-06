"""Data access for the game_events table."""

from __future__ import annotations

import json
import sqlite3

from quiver.db.models import GameEvent


def log(
    conn: sqlite3.Connection,
    event_type: str,
    team_id: int | None = None,
    details: dict | str | None = None,
) -> GameEvent:
    """Create a game event log entry."""
    # details can be a dict (auto-serialized) or a pre-formatted string
    details_str = json.dumps(details) if isinstance(details, dict) else details
    cursor = conn.execute(
        "INSERT INTO game_events (event_type, team_id, details) VALUES (?, ?, ?)",
        (event_type, team_id, details_str),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM game_events WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return GameEvent.from_row(row)


def get_all(
    conn: sqlite3.Connection,
    event_type: str | None = None,
    team_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[GameEvent]:
    """Query game events with optional filters."""
    clauses: list[str] = []
    params: list[object] = []

    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if team_id is not None:
        clauses.append("team_id = ?")
        params.append(team_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT * FROM game_events {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [GameEvent.from_row(r) for r in rows]


def count(
    conn: sqlite3.Connection,
    event_type: str | None = None,
    team_id: int | None = None,
) -> int:
    clauses: list[str] = []
    params: list[object] = []

    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if team_id is not None:
        clauses.append("team_id = ?")
        params.append(team_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM game_events {where}", params
    ).fetchone()
    return row["cnt"]
