"""Data access for the attachments table."""

from __future__ import annotations

import sqlite3

from quiver.db.models import Attachment


def create(
    conn: sqlite3.Connection,
    filename: str,
    stored_path: str,
    content_type: str | None = None,
    size_bytes: int | None = None,
    inject_id: int | None = None,
    request_id: int | None = None,
) -> Attachment:
    cursor = conn.execute(
        """INSERT INTO attachments
           (inject_id, request_id, filename, stored_path, content_type, size_bytes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (inject_id, request_id, filename, stored_path, content_type, size_bytes),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM attachments WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return Attachment.from_row(row)


def get_for_inject(conn: sqlite3.Connection, inject_id: int) -> list[Attachment]:
    rows = conn.execute(
        "SELECT * FROM attachments WHERE inject_id = ? ORDER BY id",
        (inject_id,),
    ).fetchall()
    return [Attachment.from_row(r) for r in rows]


def get_for_request(conn: sqlite3.Connection, request_id: int) -> list[Attachment]:
    rows = conn.execute(
        "SELECT * FROM attachments WHERE request_id = ? ORDER BY id",
        (request_id,),
    ).fetchall()
    return [Attachment.from_row(r) for r in rows]
