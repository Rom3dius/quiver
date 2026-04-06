"""Shared fixtures for web tests."""

from __future__ import annotations

import pytest

from quiver.config import Config
from quiver.db.connection import get_connection
from quiver.repositories import team_repo
from quiver.web.app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    config = Config(
        discord_token="test-token",
        bot_command_prefix="!",
        database_path=db_path,
        uploads_path=uploads,
        flask_host="127.0.0.1",
        flask_port=5000,
        flask_secret_key="test-secret-key",
    )
    app = create_app(config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_db(app):
    """Return a connection to the seeded test DB."""
    conn = get_connection(app.config["DATABASE_PATH"])
    yield conn
    conn.close()


@pytest.fixture
def web_teams(seeded_db):
    """All seeded teams from the web test DB.

    Separate from the root ``teams`` fixture because web tests use a
    file-backed SQLite DB (via ``app``) rather than the in-memory one.
    """
    return team_repo.get_all(seeded_db)
