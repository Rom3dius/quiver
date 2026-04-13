"""Tests for intel request repository."""

import pytest

from quiver.repositories import request_repo


def test_create_request(conn, teams):
    team = teams[0]
    req = request_repo.create(conn, team.id, "Need satellite imagery", "msg_123")
    assert req.team_id == team.id
    assert req.content == "Need satellite imagery"
    assert req.status == "pending"
    assert req.discord_message_id == "msg_123"
    assert req.response is None
    assert req.resolved_at is None


def test_get_pending(conn, teams):
    team = teams[0]
    request_repo.create(conn, team.id, "Request 1")
    request_repo.create(conn, team.id, "Request 2")

    pending = request_repo.get_pending(conn)
    assert len(pending) == 2


def test_resolve_approve(conn, teams):
    team = teams[1]
    req = request_repo.create(conn, team.id, "Agent meeting request")

    resolved = request_repo.resolve(
        conn, req.id, "approved", "Meeting approved for 0800"
    )
    assert resolved.status == "approved"
    assert resolved.response == "Meeting approved for 0800"
    assert resolved.resolved_at is not None


def test_resolve_deny(conn, teams):
    team = teams[2] if len(teams) > 2 else teams[0]
    req = request_repo.create(conn, team.id, "Risky operation")

    resolved = request_repo.resolve(conn, req.id, "denied", "Too risky")
    assert resolved.status == "denied"


def test_resolve_invalid_status(conn, teams):
    team = teams[0]
    req = request_repo.create(conn, team.id, "Something")

    with pytest.raises(ValueError, match="Invalid status"):
        request_repo.resolve(conn, req.id, "maybe")


def test_undelivered_responses(conn, teams):
    team = teams[0]
    req = request_repo.create(conn, team.id, "Intel needed")
    request_repo.resolve(conn, req.id, "approved", "Here is the intel")

    undelivered = request_repo.get_undelivered_responses(conn)
    assert len(undelivered) == 1
    assert undelivered[0].id == req.id


def test_mark_response_delivered(conn, teams):
    team = teams[1]
    req = request_repo.create(conn, team.id, "Request")
    request_repo.resolve(conn, req.id, "denied", "No")

    result = request_repo.mark_response_delivered(conn, req.id)
    assert result.response_delivered_at is not None

    undelivered = request_repo.get_undelivered_responses(conn)
    assert len(undelivered) == 0


def test_request_summary_empty(conn):
    summary = request_repo.request_summary(conn)
    assert summary == {"total": 0, "pending": 0, "approved": 0, "denied": 0}


def test_request_summary_mixed(conn, teams):
    team = teams[0]
    request_repo.create(conn, team.id, "Pending request")
    r2 = request_repo.create(conn, team.id, "Approved request")
    r3 = request_repo.create(conn, team.id, "Denied request")
    request_repo.resolve(conn, r2.id, "approved", "OK")
    request_repo.resolve(conn, r3.id, "denied", "No")

    summary = request_repo.request_summary(conn)
    assert summary["total"] == 3
    assert summary["pending"] == 1
    assert summary["approved"] == 1
    assert summary["denied"] == 1
