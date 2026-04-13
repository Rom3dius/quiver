"""Tests for game event repository."""

import json

from quiver.repositories import event_repo


def test_log_event(conn, teams):
    team = teams[0]
    event = event_repo.log(conn, "inject_sent", team.id, {"inject_id": 1})
    assert event.event_type == "inject_sent"
    assert event.team_id == team.id
    assert json.loads(event.details)["inject_id"] == 1


def test_log_event_with_string_details(conn):
    event = event_repo.log(conn, "custom_event", details="plain text details")
    assert event.details == "plain text details"


def test_log_event_without_team(conn):
    event = event_repo.log(conn, "game_start")
    assert event.team_id is None


def test_get_all_with_filters(conn, teams):
    team_a = teams[0]
    team_b = teams[1]

    event_repo.log(conn, "inject_sent", team_a.id)
    event_repo.log(conn, "request_created", team_b.id)
    event_repo.log(conn, "inject_sent", team_b.id)

    all_events = event_repo.get_all(conn)
    assert len(all_events) == 3

    inject_events = event_repo.get_all(conn, event_type="inject_sent")
    assert len(inject_events) == 2

    team_a_events = event_repo.get_all(conn, team_id=team_a.id)
    assert len(team_a_events) == 1


def test_count(conn, teams):
    team = teams[0]
    event_repo.log(conn, "inject_sent", team.id)
    event_repo.log(conn, "inject_sent", team.id)
    event_repo.log(conn, "request_created", team.id)

    assert event_repo.count(conn) == 3
    assert event_repo.count(conn, event_type="inject_sent") == 2


def test_pagination(conn):
    for i in range(10):
        event_repo.log(conn, "test_event", details=f"event_{i}")

    page1 = event_repo.get_all(conn, limit=3, offset=0)
    page2 = event_repo.get_all(conn, limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 3
    assert page1[0].id != page2[0].id


def test_get_rate_buckets(conn):
    """Rate buckets return counts grouped by minute."""
    # Events created with default 'now' all land in the same minute bucket
    event_repo.log(conn, "inject_sent")
    event_repo.log(conn, "inject_sent")
    event_repo.log(conn, "request_created")

    buckets = event_repo.get_rate_buckets(conn, minutes=30)
    assert isinstance(buckets, list)
    assert len(buckets) >= 1
    total = sum(b["count"] for b in buckets)
    assert total == 3
    # Each bucket should have the expected keys
    for b in buckets:
        assert "bucket" in b
        assert "count" in b


def test_get_rate_buckets_empty(conn):
    """No events yields empty list."""
    buckets = event_repo.get_rate_buckets(conn, minutes=5)
    assert buckets == []
