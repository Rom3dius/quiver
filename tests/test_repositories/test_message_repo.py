"""Tests for inter-team message repository."""

from quiver.repositories import message_repo, team_repo


def test_create_message(conn):
    cia = team_repo.get_by_name(conn, "CIA")
    mi6 = team_repo.get_by_name(conn, "MI6")

    msg = message_repo.create(conn, cia.id, mi6.id, "Intel to share")
    assert msg.from_team_id == cia.id
    assert msg.to_team_id == mi6.id
    assert msg.content == "Intel to share"


def test_get_all(conn):
    cia = team_repo.get_by_name(conn, "CIA")
    mi6 = team_repo.get_by_name(conn, "MI6")
    bnd = team_repo.get_by_name(conn, "BND")

    message_repo.create(conn, cia.id, mi6.id, "Message 1")
    message_repo.create(conn, mi6.id, bnd.id, "Message 2")

    messages = message_repo.get_all(conn)
    assert len(messages) == 2


def test_get_by_team(conn):
    cia = team_repo.get_by_name(conn, "CIA")
    mi6 = team_repo.get_by_name(conn, "MI6")
    bnd = team_repo.get_by_name(conn, "BND")

    message_repo.create(conn, cia.id, mi6.id, "To MI6")
    message_repo.create(conn, bnd.id, cia.id, "From BND to CIA")
    message_repo.create(conn, mi6.id, bnd.id, "MI6 to BND (not CIA)")

    cia_messages = message_repo.get_by_team(conn, cia.id)
    assert len(cia_messages) == 2  # sent one, received one
