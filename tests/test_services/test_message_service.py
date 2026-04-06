"""Tests for message service."""

from quiver.repositories import event_repo
from quiver.services import message_service


def test_send_message_logs_events_for_both_teams(conn, teams):
    team_a = teams[0]
    team_b = teams[1]

    msg = message_service.send_message(
        conn, team_a.id, team_b.id, "Sharing intel on target X"
    )
    assert msg.from_team_id == team_a.id
    assert msg.to_team_id == team_b.id

    events = event_repo.get_all(conn, event_type="inter_team_msg")
    assert len(events) == 2  # one for sender, one for receiver

    a_events = event_repo.get_all(conn, event_type="inter_team_msg", team_id=team_a.id)
    b_events = event_repo.get_all(conn, event_type="inter_team_msg", team_id=team_b.id)
    assert len(a_events) == 1
    assert len(b_events) == 1
