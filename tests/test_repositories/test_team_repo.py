"""Tests for team repository."""

from quiver.repositories import team_repo


def test_get_all_returns_seeded_teams(teams):
    assert len(teams) >= 1


def test_get_by_name_case_insensitive(conn, teams):
    first = teams[0]
    team = team_repo.get_by_name(conn, first.name.lower())
    assert team is not None
    assert team.name == first.name


def test_get_by_name_not_found(conn):
    assert team_repo.get_by_name(conn, "NONEXISTENT") is None


def test_get_by_id(conn, teams):
    team = team_repo.get_by_id(conn, teams[0].id)
    assert team is not None
    assert team.id == teams[0].id


def test_get_by_channel_id(conn, teams):
    first = teams[0]
    team = team_repo.get_by_channel_id(conn, first.discord_channel_id)
    assert team is not None
    assert team.name == first.name


def test_update_channel_id(conn, teams):
    team = teams[0]
    updated = team_repo.update_channel_id(conn, team.id, "123456789")
    assert updated.discord_channel_id == "123456789"


def test_teams_are_frozen(teams):
    team = teams[0]
    try:
        team.name = "FBI"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass
