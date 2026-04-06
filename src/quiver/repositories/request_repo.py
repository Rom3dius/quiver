"""Data access for the intel_requests table."""

from __future__ import annotations

import sqlite3

from quiver.db.models import IntelRequest


def create(
    conn: sqlite3.Connection,
    team_id: int,
    content: str,
    discord_message_id: str | None = None,
) -> IntelRequest:
    cursor = conn.execute(
        """INSERT INTO intel_requests (team_id, content, discord_message_id)
           VALUES (?, ?, ?)""",
        (team_id, content, discord_message_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM intel_requests WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return IntelRequest.from_row(row)


def get_by_id(conn: sqlite3.Connection, request_id: int) -> IntelRequest | None:
    row = conn.execute(
        "SELECT * FROM intel_requests WHERE id = ?", (request_id,)
    ).fetchone()
    return IntelRequest.from_row(row) if row else None


def get_pending(conn: sqlite3.Connection) -> list[IntelRequest]:
    rows = conn.execute(
        "SELECT * FROM intel_requests WHERE status = 'pending' ORDER BY created_at"
    ).fetchall()
    return [IntelRequest.from_row(r) for r in rows]


def get_all(
    conn: sqlite3.Connection, limit: int = 100, offset: int = 0
) -> list[IntelRequest]:
    rows = conn.execute(
        "SELECT * FROM intel_requests ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [IntelRequest.from_row(r) for r in rows]


def count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) as cnt FROM intel_requests").fetchone()
    return row["cnt"]


def resolve(
    conn: sqlite3.Connection,
    request_id: int,
    status: str,
    response: str | None = None,
) -> IntelRequest | None:
    """Mark a request as approved or denied with an optional response."""
    if status not in ("approved", "denied"):
        raise ValueError(f"Invalid status: {status}. Must be 'approved' or 'denied'.")
    conn.execute(
        """UPDATE intel_requests
           SET status = ?, response = ?,
               resolved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE id = ?""",
        (status, response, request_id),
    )
    conn.commit()
    return get_by_id(conn, request_id)


def get_undelivered_responses(conn: sqlite3.Connection) -> list[IntelRequest]:
    """Get resolved requests whose response has not been delivered to Discord.

    The bot's delivery loop polls this to find responses awaiting dispatch.
    """
    rows = conn.execute(
        """SELECT * FROM intel_requests
           WHERE status != 'pending'
             AND response_delivered_at IS NULL
           ORDER BY resolved_at"""
    ).fetchall()
    return [IntelRequest.from_row(r) for r in rows]


def mark_response_delivered(
    conn: sqlite3.Connection, request_id: int
) -> IntelRequest | None:
    conn.execute(
        """UPDATE intel_requests
           SET response_delivered_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE id = ?""",
        (request_id,),
    )
    conn.commit()
    return get_by_id(conn, request_id)
