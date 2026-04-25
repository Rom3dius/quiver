"""Apply database schema and optional seed data."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

_SQL_DIR = Path(__file__).parent

logger = logging.getLogger("quiver.db.migrate")


def apply_schema(conn: sqlite3.Connection) -> None:
    """Execute schema.sql to create all tables idempotently."""
    schema_sql = (_SQL_DIR / "schema.sql").read_text()
    conn.executescript(schema_sql)


def _migrate_attachments_message_id(conn: sqlite3.Connection) -> None:
    """Add message_id column to attachments if it doesn't exist yet.

    Existing databases created before inter-team message attachments were
    added won't have this column.  SQLite requires table recreation to
    update CHECK constraints, so we copy data through a temp table.
    """
    cols = [row[1] for row in conn.execute("PRAGMA table_info(attachments)").fetchall()]
    if "message_id" in cols:
        return

    logger.info("Migrating attachments table: adding message_id column")
    conn.executescript(
        """
        ALTER TABLE attachments RENAME TO _attachments_old;

        CREATE TABLE attachments (
            id           INTEGER PRIMARY KEY,
            inject_id    INTEGER REFERENCES injects(id),
            request_id   INTEGER REFERENCES intel_requests(id),
            message_id   INTEGER REFERENCES inter_team_messages(id),
            filename     TEXT NOT NULL,
            stored_path  TEXT NOT NULL,
            content_type TEXT,
            size_bytes   INTEGER,
            created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            CHECK(
                (inject_id IS NOT NULL AND request_id IS NULL AND message_id IS NULL) OR
                (inject_id IS NULL AND request_id IS NOT NULL AND message_id IS NULL) OR
                (inject_id IS NULL AND request_id IS NULL AND message_id IS NOT NULL)
            )
        );

        INSERT INTO attachments
            (id, inject_id, request_id, message_id, filename, stored_path,
             content_type, size_bytes, created_at)
        SELECT id, inject_id, request_id, NULL, filename, stored_path,
               content_type, size_bytes, created_at
        FROM _attachments_old;

        DROP TABLE _attachments_old;

        CREATE INDEX IF NOT EXISTS idx_attachments_inject
            ON attachments(inject_id) WHERE inject_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_attachments_request
            ON attachments(request_id) WHERE request_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_attachments_message
            ON attachments(message_id) WHERE message_id IS NOT NULL;
    """
    )


def apply_seed(conn: sqlite3.Connection) -> None:
    """Insert seed data (17 teams) idempotently via INSERT OR IGNORE."""
    seed_sql = (_SQL_DIR / "seed.sql").read_text()
    conn.executescript(seed_sql)


def init_db(conn: sqlite3.Connection) -> None:
    """Apply schema, run migrations, and seed data."""
    apply_schema(conn)
    _migrate_attachments_message_id(conn)
    apply_seed(conn)
