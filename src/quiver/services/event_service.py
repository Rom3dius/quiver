"""Convenience wrapper around event_repo for the web layer."""

from __future__ import annotations

import sqlite3

from quiver.db.models import GameEvent
from quiver.repositories import event_repo


def get_events(
    conn: sqlite3.Connection,
    event_type: str | None = None,
    team_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[GameEvent]:
    return event_repo.get_all(conn, event_type, team_id, limit, offset)


def count_events(
    conn: sqlite3.Connection,
    event_type: str | None = None,
    team_id: int | None = None,
) -> int:
    return event_repo.count(conn, event_type, team_id)
