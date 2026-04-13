"""Data access for the inter_team_messages table."""

from __future__ import annotations

import sqlite3

from quiver.db.models import InterTeamMessage


def create(
    conn: sqlite3.Connection,
    from_team_id: int,
    to_team_id: int,
    content: str,
) -> InterTeamMessage:
    cursor = conn.execute(
        """INSERT INTO inter_team_messages (from_team_id, to_team_id, content)
           VALUES (?, ?, ?)""",
        (from_team_id, to_team_id, content),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM inter_team_messages WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return InterTeamMessage.from_row(row)


def get_by_id(conn: sqlite3.Connection, message_id: int) -> InterTeamMessage | None:
    row = conn.execute(
        "SELECT * FROM inter_team_messages WHERE id = ?", (message_id,)
    ).fetchone()
    return InterTeamMessage.from_row(row) if row else None


def get_all(conn: sqlite3.Connection, limit: int = 100) -> list[InterTeamMessage]:
    rows = conn.execute(
        "SELECT * FROM inter_team_messages ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [InterTeamMessage.from_row(r) for r in rows]


def count(conn: sqlite3.Connection) -> int:
    """Total inter-team messages."""
    row = conn.execute("SELECT COUNT(*) as cnt FROM inter_team_messages").fetchone()
    return row["cnt"]


def get_by_team(
    conn: sqlite3.Connection, team_id: int, limit: int = 50
) -> list[InterTeamMessage]:
    """Get messages where team is sender or receiver."""
    rows = conn.execute(
        """SELECT * FROM inter_team_messages
           WHERE from_team_id = ? OR to_team_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (team_id, team_id, limit),
    ).fetchall()
    return [InterTeamMessage.from_row(r) for r in rows]


def get_comm_matrix(conn: sqlite3.Connection) -> list[tuple[int, int, int]]:
    """Return (from_team_id, to_team_id, message_count) for all team pairs."""
    rows = conn.execute(
        """SELECT from_team_id, to_team_id, COUNT(*) as cnt
           FROM inter_team_messages
           GROUP BY from_team_id, to_team_id"""
    ).fetchall()
    return [(r["from_team_id"], r["to_team_id"], r["cnt"]) for r in rows]
