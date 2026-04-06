"""Shared test fixtures using in-memory SQLite."""

from __future__ import annotations

import sqlite3

import pytest

from quiver.db.connection import get_connection
from quiver.db.migrate import init_db
from quiver.repositories import team_repo


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory SQLite connection with schema and seed data applied."""
    connection = get_connection(":memory:")
    init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def teams(conn):
    """All seeded teams, ordered by ID.  Use teams[0], teams[1], etc.

    Tests should never hard-code team names or counts from seed.sql.
    Instead, index into this list so they stay resilient when the seed
    data changes.
    """
    return team_repo.get_all(conn)
