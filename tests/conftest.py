"""Shared test fixtures using in-memory SQLite."""

from __future__ import annotations

import sqlite3

import pytest

from quiver.db.connection import get_connection
from quiver.db.migrate import init_db


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory SQLite connection with schema and seed data applied."""
    connection = get_connection(":memory:")
    init_db(connection)
    yield connection
    connection.close()
