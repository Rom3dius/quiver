"""Tests for inject repository."""

from quiver.repositories import inject_repo, team_repo


def test_create_inject_with_recipients(conn):
    teams = team_repo.get_all(conn)
    team_ids = [teams[0].id, teams[1].id]

    inject = inject_repo.create(conn, "Test inject content", team_ids)
    assert inject.content == "Test inject content"
    assert inject.sent_by_operator == "C2"

    recipients = inject_repo.get_recipients(conn, inject.id)
    assert len(recipients) == 2
    assert all(r.delivered_at is None for r in recipients)


def test_get_undelivered_recipients(conn):
    teams = team_repo.get_all(conn)
    inject_repo.create(conn, "Inject 1", [teams[0].id])
    inject_repo.create(conn, "Inject 2", [teams[1].id, teams[2].id])

    undelivered = inject_repo.get_undelivered_recipients(conn)
    assert len(undelivered) == 3


def test_mark_delivered(conn):
    teams = team_repo.get_all(conn)
    inject_repo.create(conn, "Inject", [teams[0].id])

    undelivered = inject_repo.get_undelivered_recipients(conn)
    assert len(undelivered) == 1

    result = inject_repo.mark_delivered(conn, undelivered[0].id)
    assert result.delivered_at is not None

    undelivered_after = inject_repo.get_undelivered_recipients(conn)
    assert len(undelivered_after) == 0


def test_get_all_injects(conn):
    teams = team_repo.get_all(conn)
    inject_repo.create(conn, "First", [teams[0].id])
    inject_repo.create(conn, "Second", [teams[1].id])

    all_injects = inject_repo.get_all(conn)
    assert len(all_injects) == 2
    contents = {i.content for i in all_injects}
    assert contents == {"First", "Second"}


def test_get_by_id(conn):
    teams = team_repo.get_all(conn)
    inject = inject_repo.create(conn, "Find me", [teams[0].id])
    found = inject_repo.get_by_id(conn, inject.id)
    assert found is not None
    assert found.content == "Find me"
