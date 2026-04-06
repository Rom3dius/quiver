"""File upload handling — save to disk and record in DB."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from quiver.db.models import Attachment
from quiver.repositories import attachment_repo


def save_upload(
    conn: sqlite3.Connection,
    uploads_path: Path,
    file: FileStorage,
    inject_id: int | None = None,
    request_id: int | None = None,
) -> Attachment:
    """Save an uploaded file to disk and record it in the database."""
    original_name = secure_filename(file.filename or "unnamed")
    # 12-char UUID prefix prevents filename collisions when multiple teams
    # upload files with the same name (e.g. "report.pdf").  The original
    # name is preserved in the DB for display; only the on-disk name changes.
    unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"
    dest = uploads_path / unique_name

    file.save(str(dest))
    size = dest.stat().st_size

    return attachment_repo.create(
        conn,
        filename=original_name,
        stored_path=str(dest),
        content_type=file.content_type,
        size_bytes=size,
        inject_id=inject_id,
        request_id=request_id,
    )


def save_uploads(
    conn: sqlite3.Connection,
    uploads_path: Path,
    files: list[FileStorage],
    inject_id: int | None = None,
    request_id: int | None = None,
) -> list[Attachment]:
    """Save multiple uploaded files."""
    attachments = []
    for f in files:
        if f.filename:  # Skip empty file inputs
            att = save_upload(conn, uploads_path, f, inject_id, request_id)
            attachments.append(att)
    return attachments
