"""Tests for inject service."""

from quiver.repositories import event_repo, inject_repo
from quiver.services import inject_service


def test_send_inject_creates_inject_and_events(conn, teams):
    team_ids = [t.id for t in teams[:3]]

    inject = inject_service.send_inject(
        conn, "Flash intel report", team_ids, "Operator1"
    )
    assert inject.content == "Flash intel report"
    assert inject.sent_by_operator == "Operator1"

    recipients = inject_repo.get_recipients(conn, inject.id)
    assert len(recipients) == len(team_ids)

    events = event_repo.get_all(conn, event_type="inject_sent")
    assert len(events) == len(team_ids)


def test_mark_delivered_logs_event(conn, teams):
    inject_service.send_inject(conn, "Deliver me", [teams[0].id])

    undelivered = inject_repo.get_undelivered_recipients(conn)
    result = inject_service.mark_delivered(conn, undelivered[0])
    assert result.delivered_at is not None

    events = event_repo.get_all(conn, event_type="inject_delivered")
    assert len(events) == 1
