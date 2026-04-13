"""Tests for error handling and hardening features."""

from __future__ import annotations

import json

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


def test_bot_status_in_pulse_no_heartbeat(client):
    """Pulse endpoint should report bot status even with stale heartbeat."""
    resp = client.get("/pulse")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "bot" in data
    assert "online" in data["bot"]


def test_bot_status_in_pulse_after_beat(client, app):
    """Pulse endpoint should show bot online after a fresh heartbeat."""
    conn = get_connection(app.config["DATABASE_PATH"])
    try:
        heartbeat_repo.beat(conn, guild_count=1)
    finally:
        conn.close()

    resp = client.get("/pulse")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["bot"]["online"] is True


def test_dashboard_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"COMMAND" in resp.data
