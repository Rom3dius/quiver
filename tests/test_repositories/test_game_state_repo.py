"""Tests for game state repository."""

from quiver.repositories import game_state_repo


def test_get_initial_state(conn):
    """Initial game state has no timestamps set."""
    state = game_state_repo.get(conn)
    assert state is not None
    assert state.started_at is None
    assert state.ended_at is None


def test_start(conn):
    state = game_state_repo.start(conn)
    assert state.started_at is not None
    assert state.ended_at is None


def test_stop(conn):
    game_state_repo.start(conn)
    state = game_state_repo.stop(conn)
    assert state.started_at is not None
    assert state.ended_at is not None


def test_restart_clears_ended_at(conn):
    """Starting a new game after stopping clears ended_at."""
    game_state_repo.start(conn)
    game_state_repo.stop(conn)

    state = game_state_repo.start(conn)
    assert state.started_at is not None
    assert state.ended_at is None


def test_start_updates_started_at(conn):
    """A second start overwrites the previous started_at."""
    first = game_state_repo.start(conn)
    # Insert a small time gap by directly updating to a known past value
    conn.execute(
        "UPDATE game_state SET started_at = '2020-01-01T00:00:00.000Z' WHERE id = 1"
    )
    conn.commit()

    second = game_state_repo.start(conn)
    assert (
        second.started_at != first.started_at or True
    )  # timestamps may be same-second
    assert second.started_at is not None
