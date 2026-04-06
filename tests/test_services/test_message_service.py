"""Tests for message service."""

from quiver.repositories import event_repo, team_repo
from quiver.services import message_service


def test_send_message_logs_events_for_both_teams(conn):
    cia = team_repo.get_by_name(conn, "CIA")
    mi6 = team_repo.get_by_name(conn, "MI6")

    msg = message_service.send_message(
        conn, cia.id, mi6.id, "Sharing intel on target X"
    )
    assert msg.from_team_id == cia.id
    assert msg.to_team_id == mi6.id

    events = event_repo.get_all(conn, event_type="inter_team_msg")
    assert len(events) == 2  # one for sender, one for receiver

    cia_events = event_repo.get_all(conn, event_type="inter_team_msg", team_id=cia.id)
    mi6_events = event_repo.get_all(conn, event_type="inter_team_msg", team_id=mi6.id)
    assert len(cia_events) == 1
    assert len(mi6_events) == 1
