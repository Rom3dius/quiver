"""Data access for injects and inject_recipients tables."""

from __future__ import annotations

import sqlite3

from quiver.db.models import Inject, InjectRecipient


def create(
    conn: sqlite3.Connection,
    content: str,
    team_ids: list[int],
    operator: str = "C2",
) -> Inject:
    """Create an inject and its recipient rows. Returns the new Inject."""
    cursor = conn.execute(
        "INSERT INTO injects (content, sent_by_operator) VALUES (?, ?)",
        (content, operator),
    )
    inject_id = cursor.lastrowid
    # One recipient row per team; the delivery loop picks these up
    for team_id in team_ids:
        conn.execute(
            "INSERT INTO inject_recipients (inject_id, team_id) VALUES (?, ?)",
            (inject_id, team_id),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM injects WHERE id = ?", (inject_id,)).fetchone()
    return Inject.from_row(row)


def get_by_id(conn: sqlite3.Connection, inject_id: int) -> Inject | None:
    row = conn.execute("SELECT * FROM injects WHERE id = ?", (inject_id,)).fetchone()
    return Inject.from_row(row) if row else None


def get_all(
    conn: sqlite3.Connection, limit: int = 100, offset: int = 0
) -> list[Inject]:
    rows = conn.execute(
        "SELECT * FROM injects ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [Inject.from_row(r) for r in rows]


def count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) as cnt FROM injects").fetchone()
    return row["cnt"]


def get_recipients(conn: sqlite3.Connection, inject_id: int) -> list[InjectRecipient]:
    rows = conn.execute(
        "SELECT * FROM inject_recipients WHERE inject_id = ?", (inject_id,)
    ).fetchall()
    return [InjectRecipient.from_row(r) for r in rows]


def get_undelivered_recipients(conn: sqlite3.Connection) -> list[InjectRecipient]:
    """Get all inject recipients that have not been delivered yet."""
    rows = conn.execute(
        "SELECT * FROM inject_recipients WHERE delivered_at IS NULL"
    ).fetchall()
    return [InjectRecipient.from_row(r) for r in rows]


def mark_delivered(
    conn: sqlite3.Connection, recipient_id: int
) -> InjectRecipient | None:
    conn.execute(
        """UPDATE inject_recipients
           SET delivered_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE id = ?""",
        (recipient_id,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM inject_recipients WHERE id = ?", (recipient_id,)
    ).fetchone()
    return InjectRecipient.from_row(row) if row else None
