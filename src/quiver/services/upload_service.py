"""File upload handling — save to disk and record in DB."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from quiver.db.models import Attachment
from quiver.repositories import attachment_repo
from quiver.validation import (
    MAX_FILE_SIZE_BYTES,
    infer_content_type,
    validate_file_extension,
)

logger = logging.getLogger("quiver.upload")


class UploadValidationError(ValueError):
    """Raised when an uploaded file fails validation."""


def save_upload(
    conn: sqlite3.Connection,
    uploads_path: Path,
    file: FileStorage,
    inject_id: int | None = None,
    request_id: int | None = None,
) -> Attachment:
    """Save an uploaded file to disk and record it in the database.

    Raises UploadValidationError if the file fails extension or size checks.
    """
    original_name = secure_filename(file.filename or "unnamed")

    # Validate file extension against allowlist
    ext_error = validate_file_extension(original_name)
    if ext_error is not None:
        raise UploadValidationError(ext_error)

    # 12-char UUID prefix prevents filename collisions when multiple teams
    # upload files with the same name (e.g. "report.pdf").  The original
    # name is preserved in the DB for display; only the on-disk name changes.
    unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"
    dest = uploads_path / unique_name

    file.save(str(dest))
    size = dest.stat().st_size

    # Enforce per-file size limit after saving (so we get the real size)
    if size > MAX_FILE_SIZE_BYTES:
        dest.unlink(missing_ok=True)
        raise UploadValidationError(
            f"File '{original_name}' is too large "
            f"({size // (1024 * 1024)} MB, max {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)."
        )

    # Validate and normalise content_type — don't trust the client header blindly
    content_type = infer_content_type(original_name, file.content_type)

    return attachment_repo.create(
        conn,
        filename=original_name,
        stored_path=str(dest),
        content_type=content_type,
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
    """Save multiple uploaded files.

    Returns successfully saved attachments.  Logs warnings for files that
    fail validation rather than aborting the entire batch.
    """
    attachments = []
    for f in files:
        if f.filename:  # Skip empty file inputs
            try:
                att = save_upload(conn, uploads_path, f, inject_id, request_id)
                attachments.append(att)
            except UploadValidationError as exc:
                logger.warning("Upload rejected: %s", exc)
    return attachments
