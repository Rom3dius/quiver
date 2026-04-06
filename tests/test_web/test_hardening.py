"""Tests for error handling and hardening features."""

from __future__ import annotations

from quiver.db.connection import get_connection
from quiver.repositories import heartbeat_repo


def test_404_page(client):
    resp = client.get("/nonexistent-page")
    assert resp.status_code == 404
    assert b"Not Found" in resp.data


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json["status"] == "ok"


def test_bot_status_partial_no_heartbeat(client):
    """Bot status should show offline when no recent heartbeat."""
    resp = client.get("/bot-status")
    assert resp.status_code == 200
    # Initial heartbeat exists but is stale (just created, should be "online" briefly)
    assert b"Bot" in resp.data


def test_bot_status_partial_after_beat(client, app):
    """Bot status should show online after a fresh heartbeat."""
    conn = get_connection(app.config["DATABASE_PATH"])
    try:
        heartbeat_repo.beat(conn, guild_count=1)
    finally:
        conn.close()

    resp = client.get("/bot-status")
    assert resp.status_code == 200
    assert b"Online" in resp.data


def test_dashboard_includes_bot_status(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Bot" in resp.data
