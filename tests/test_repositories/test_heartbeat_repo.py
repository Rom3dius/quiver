"""Tests for heartbeat repository."""

from quiver.repositories import heartbeat_repo


def test_initial_heartbeat_exists(conn):
    hb = heartbeat_repo.get(conn)
    assert hb is not None
    assert hb.guild_count == 0


def test_beat_updates_timestamp(conn):
    hb_before = heartbeat_repo.get(conn)
    heartbeat_repo.beat(conn, guild_count=3)
    hb_after = heartbeat_repo.get(conn)

    assert hb_after.guild_count == 3
    assert hb_after.last_beat >= hb_before.last_beat
