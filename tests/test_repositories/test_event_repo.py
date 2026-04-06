"""Tests for game event repository."""

import json

from quiver.repositories import event_repo, team_repo


def test_log_event(conn):
    team = team_repo.get_by_name(conn, "CIA")
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


def test_get_all_with_filters(conn):
    cia = team_repo.get_by_name(conn, "CIA")
    mi6 = team_repo.get_by_name(conn, "MI6")

    event_repo.log(conn, "inject_sent", cia.id)
    event_repo.log(conn, "request_created", mi6.id)
    event_repo.log(conn, "inject_sent", mi6.id)

    all_events = event_repo.get_all(conn)
    assert len(all_events) == 3

    inject_events = event_repo.get_all(conn, event_type="inject_sent")
    assert len(inject_events) == 2

    cia_events = event_repo.get_all(conn, team_id=cia.id)
    assert len(cia_events) == 1


def test_count(conn):
    cia = team_repo.get_by_name(conn, "CIA")
    event_repo.log(conn, "inject_sent", cia.id)
    event_repo.log(conn, "inject_sent", cia.id)
    event_repo.log(conn, "request_created", cia.id)

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
