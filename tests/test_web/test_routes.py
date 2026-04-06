"""Tests for web dashboard routes."""

from __future__ import annotations

from quiver.services import inject_service, request_service

# --- Dashboard ---


def test_dashboard_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Command" in resp.data
    assert b"Dashboard" in resp.data


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json["status"] == "ok"


# --- Injects ---


def test_inject_page_loads(client, web_teams):
    resp = client.get("/injects/")
    assert resp.status_code == 200
    assert b"Inject Composer" in resp.data
    # At least one team checkbox should be rendered
    assert web_teams[0].name.encode() in resp.data


def test_create_inject(client, seeded_db, web_teams):
    team_ids = [web_teams[0].id, web_teams[1].id]

    resp = client.post(
        "/injects/",
        data={
            "content": "Flash intel: target spotted in Berlin",
            "operator": "TestOp",
            "team_ids": team_ids,
        },
    )
    assert resp.status_code == 200
    assert b"sent to" in resp.data


def test_create_inject_empty_content(client):
    resp = client.post(
        "/injects/",
        data={
            "content": "",
            "team_ids": [1],
        },
    )
    assert resp.status_code == 200
    assert b"cannot be empty" in resp.data


def test_create_inject_no_teams(client):
    resp = client.post(
        "/injects/",
        data={
            "content": "Some inject",
        },
    )
    assert resp.status_code == 200
    assert b"Select at least one" in resp.data


def test_inject_history_partial(client, seeded_db, web_teams):
    inject_service.send_inject(seeded_db, "Test inject", [web_teams[0].id])

    resp = client.get("/injects/history")
    assert resp.status_code == 200
    assert b"Test inject" in resp.data


# --- Requests ---


def test_request_page_loads(client):
    resp = client.get("/requests/")
    assert resp.status_code == 200
    assert b"Intel Request Queue" in resp.data


def test_request_queue_partial(client, seeded_db, web_teams):
    team = web_teams[0]
    request_service.create_request(seeded_db, team.id, "Need satellite imagery")

    resp = client.get("/requests/queue")
    assert resp.status_code == 200
    assert b"satellite imagery" in resp.data
    assert team.name.encode() in resp.data


def test_resolve_request_approve(client, seeded_db, web_teams):
    team = web_teams[0]
    req = request_service.create_request(seeded_db, team.id, "Agent meeting")

    resp = client.post(
        f"/requests/{req.id}/resolve",
        data={
            "status": "approved",
            "response": "Meeting confirmed for 0800Z",
        },
    )
    assert resp.status_code == 200
    assert b"APPROVED" in resp.data


def test_resolve_request_deny(client, seeded_db, web_teams):
    team = web_teams[1]
    req = request_service.create_request(seeded_db, team.id, "Risky operation")

    resp = client.post(
        f"/requests/{req.id}/resolve",
        data={
            "status": "denied",
            "response": "Too risky",
        },
    )
    assert resp.status_code == 200
    assert b"DENIED" in resp.data


def test_resolve_request_invalid_status(client, seeded_db, web_teams):
    team = web_teams[0]
    req = request_service.create_request(seeded_db, team.id, "Something")

    resp = client.post(
        f"/requests/{req.id}/resolve",
        data={
            "status": "maybe",
        },
    )
    assert resp.status_code == 200
    assert b"Invalid status" in resp.data


def test_all_requests_partial(client, seeded_db, web_teams):
    team = web_teams[0]
    for i in range(3):
        request_service.create_request(seeded_db, team.id, f"Request {i}")

    resp = client.get("/requests/all?page=1")
    assert resp.status_code == 200
    assert b"Request" in resp.data


def test_inject_history_partial_paginated(client, seeded_db, web_teams):
    team = web_teams[0]
    for i in range(3):
        inject_service.send_inject(seeded_db, f"Inject {i}", [team.id])

    resp = client.get("/injects/history?page=1")
    assert resp.status_code == 200
    assert b"Inject" in resp.data


# --- Game Log ---


def test_game_log_page_loads(client):
    resp = client.get("/log/")
    assert resp.status_code == 200
    assert b"Game Log" in resp.data


def test_game_log_with_events(client, seeded_db, web_teams):
    inject_service.send_inject(seeded_db, "Test inject", [web_teams[0].id])

    resp = client.get("/log/")
    assert resp.status_code == 200
    assert b"inject_sent" in resp.data


def test_game_log_filter_by_type(client, seeded_db, web_teams):
    team = web_teams[0]
    inject_service.send_inject(seeded_db, "Inject", [team.id])
    request_service.create_request(seeded_db, team.id, "Request")

    resp = client.get("/log/?event_type=inject_sent")
    assert resp.status_code == 200
    assert b"inject_sent" in resp.data


def test_game_log_partial(client, seeded_db, web_teams):
    inject_service.send_inject(seeded_db, "Partial test", [web_teams[0].id])

    resp = client.get("/log/partial?limit=5")
    assert resp.status_code == 200


# --- Teams ---


def test_teams_page_loads(client, web_teams):
    resp = client.get("/teams/")
    assert resp.status_code == 200
    assert b"Team Overview" in resp.data
    # All seeded teams should appear
    for team in web_teams:
        assert team.name.encode() in resp.data


def test_teams_show_channel_status(client):
    resp = client.get("/teams/")
    assert resp.status_code == 200
    # All teams have real channel IDs now
    assert b"Configured" in resp.data
