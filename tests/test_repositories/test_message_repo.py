"""Tests for inter-team message repository."""

from quiver.repositories import message_repo


def test_create_message(conn, teams):
    team_a = teams[0]
    team_b = teams[1]

    msg = message_repo.create(conn, team_a.id, team_b.id, "Intel to share")
    assert msg.from_team_id == team_a.id
    assert msg.to_team_id == team_b.id
    assert msg.content == "Intel to share"


def test_get_all(conn, teams):
    team_a, team_b, team_c = teams[0], teams[1], teams[2]

    message_repo.create(conn, team_a.id, team_b.id, "Message 1")
    message_repo.create(conn, team_b.id, team_c.id, "Message 2")

    messages = message_repo.get_all(conn)
    assert len(messages) == 2


def test_get_by_team(conn, teams):
    team_a, team_b, team_c = teams[0], teams[1], teams[2]

    message_repo.create(conn, team_a.id, team_b.id, "To B")
    message_repo.create(conn, team_c.id, team_a.id, "From C to A")
    message_repo.create(conn, team_b.id, team_c.id, "B to C (not A)")

    team_a_messages = message_repo.get_by_team(conn, team_a.id)
    assert len(team_a_messages) == 2  # sent one, received one


def test_count_empty(conn):
    assert message_repo.count(conn) == 0


def test_count(conn, teams):
    team_a, team_b = teams[0], teams[1]
    message_repo.create(conn, team_a.id, team_b.id, "Message 1")
    message_repo.create(conn, team_b.id, team_a.id, "Message 2")
    assert message_repo.count(conn) == 2


def test_get_comm_matrix_empty(conn):
    assert message_repo.get_comm_matrix(conn) == []


def test_get_comm_matrix(conn, teams):
    team_a, team_b, team_c = teams[0], teams[1], teams[2]

    message_repo.create(conn, team_a.id, team_b.id, "Msg 1")
    message_repo.create(conn, team_a.id, team_b.id, "Msg 2")
    message_repo.create(conn, team_b.id, team_c.id, "Msg 3")

    matrix = message_repo.get_comm_matrix(conn)
    assert len(matrix) == 2

    # Each entry is (from_team_id, to_team_id, count)
    lookup = {(frm, to): cnt for frm, to, cnt in matrix}
    assert lookup[(team_a.id, team_b.id)] == 2
    assert lookup[(team_b.id, team_c.id)] == 1
