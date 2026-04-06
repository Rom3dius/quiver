"""Tests for team repository."""

from quiver.repositories import team_repo


def test_get_all_returns_seeded_teams(conn):
    teams = team_repo.get_all(conn)
    assert len(teams) == 4


def test_get_by_name_case_insensitive(conn):
    team = team_repo.get_by_name(conn, "cia")
    assert team is not None
    assert team.name == "CIA"


def test_get_by_name_not_found(conn):
    assert team_repo.get_by_name(conn, "NONEXISTENT") is None


def test_get_by_id(conn):
    teams = team_repo.get_all(conn)
    team = team_repo.get_by_id(conn, teams[0].id)
    assert team is not None
    assert team.id == teams[0].id


def test_get_by_channel_id(conn):
    team = team_repo.get_by_channel_id(conn, "1490331775153737829")
    assert team is not None
    assert team.name == "CIA"


def test_update_channel_id(conn):
    team = team_repo.get_by_name(conn, "CIA")
    updated = team_repo.update_channel_id(conn, team.id, "123456789")
    assert updated.discord_channel_id == "123456789"


def test_teams_are_frozen(conn):
    team = team_repo.get_by_name(conn, "CIA")
    try:
        team.name = "FBI"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass
