"""Tests for request service."""

from quiver.repositories import event_repo, team_repo
from quiver.services import request_service


def test_create_request_logs_event(conn):
    team = team_repo.get_by_name(conn, "CIA")
    req = request_service.create_request(conn, team.id, "Need HUMINT on target")

    assert req.status == "pending"
    events = event_repo.get_all(conn, event_type="request_created")
    assert len(events) == 1


def test_resolve_request_logs_event(conn):
    team = team_repo.get_by_name(conn, "MI6")
    req = request_service.create_request(conn, team.id, "Satellite pass requested")

    resolved = request_service.resolve_request(
        conn, req.id, "approved", "Pass scheduled for 1400Z"
    )
    assert resolved.status == "approved"
    assert resolved.response == "Pass scheduled for 1400Z"

    events = event_repo.get_all(conn, event_type="request_resolved")
    assert len(events) == 1


def test_mark_response_delivered_logs_event(conn):
    team = team_repo.get_by_name(conn, "BND")
    req = request_service.create_request(conn, team.id, "Request")
    request_service.resolve_request(conn, req.id, "denied", "Denied")

    result = request_service.mark_response_delivered(conn, req.id)
    assert result.response_delivered_at is not None

    events = event_repo.get_all(conn, event_type="response_delivered")
    assert len(events) == 1
