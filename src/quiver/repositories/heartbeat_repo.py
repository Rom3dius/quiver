"""Data access for the bot_heartbeat table."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from quiver.db.models import _parse_ts


@dataclass(frozen=True)
class Heartbeat:
    last_beat: datetime
    guild_count: int

    @classmethod
    def from_row(cls, row: dict | object) -> Heartbeat:
        r = dict(row)
        return cls(
            last_beat=_parse_ts(r["last_beat"]),  # type: ignore[arg-type]
            guild_count=r["guild_count"],
        )


def beat(conn: sqlite3.Connection, guild_count: int = 0) -> None:
    """Update the single-row heartbeat timestamp.

    Always id=1 -- the seed data inserts the row; we only ever UPDATE.
    """
    conn.execute(
        """UPDATE bot_heartbeat
           SET last_beat = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
               guild_count = ?
           WHERE id = 1""",
        (guild_count,),
    )
    conn.commit()


def get(conn: sqlite3.Connection) -> Heartbeat | None:
    row = conn.execute("SELECT * FROM bot_heartbeat WHERE id = 1").fetchone()
    return Heartbeat.from_row(row) if row else None
