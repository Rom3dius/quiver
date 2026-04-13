"""Tests for the messaging cog logic."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.messaging import Messaging, _send_to_teams
from quiver.db.connection import get_connection
from quiver.repositories import team_repo


@pytest.fixture
def db_path(tmp_path, conn):
    path = tmp_path / "test.db"
    file_conn = sqlite3.connect(str(path))
    conn.backup(file_conn)
    file_conn.close()
    return str(path)


@pytest.fixture
def bot(db_path):
    mock_bot = MagicMock()
    mock_bot.quiver_db_path = db_path
    return mock_bot


def _setup_teams(db_path: str, teams) -> tuple[int, int, int]:
    """Assign channel IDs to the first 3 seeded teams and return those IDs."""
    conn = get_connection(db_path)
    try:
        for i, ch_id in enumerate(["100", "200", "300"]):
            team = team_repo.get_by_name(conn, teams[i].name)
            team_repo.update_channel_id(conn, team.id, ch_id)
    finally:
        conn.close()
    return 100, 200, 300


@pytest.mark.asyncio
async def test_send_single_team(bot, db_path, teams):
    team_b = teams[1]
    ch_a, ch_b, _ = _setup_teams(db_path, teams)

    mock_channel = AsyncMock(spec=discord.TextChannel)
    bot.get_channel = lambda cid: mock_channel if cid == ch_b else None

    result = await _send_to_teams(bot, ch_a, [team_b.name], "Intel to share")

    mock_channel.send.assert_called_once()
    assert team_b.name in result.description


@pytest.mark.asyncio
async def test_send_multiple_teams(bot, db_path, teams):
    team_b, team_c = teams[1], teams[2]
    ch_a, ch_b, ch_c = _setup_teams(db_path, teams)

    channels = {
        ch_b: AsyncMock(spec=discord.TextChannel),
        ch_c: AsyncMock(spec=discord.TextChannel),
    }
    bot.get_channel = lambda cid: channels.get(cid)

    result = await _send_to_teams(
        bot, ch_a, [team_b.name, team_c.name], "Joint briefing"
    )

    channels[ch_b].send.assert_called_once()
    channels[ch_c].send.assert_called_once()
    assert team_b.name in result.description
    assert team_c.name in result.description


@pytest.mark.asyncio
async def test_send_unknown_target(bot, db_path, teams):
    _setup_teams(db_path, teams)

    result = await _send_to_teams(bot, 100, ["NONEXISTENT"], "Hello")
    assert "not found" in result.description


@pytest.mark.asyncio
async def test_send_to_self(bot, db_path, teams):
    team_a = teams[0]
    _setup_teams(db_path, teams)

    result = await _send_to_teams(bot, 100, [team_a.name], "Talking to myself")
    assert "own team" in result.description


@pytest.mark.asyncio
async def test_partial_failure(bot, db_path, teams):
    team_b = teams[1]
    ch_a, ch_b, _ = _setup_teams(db_path, teams)

    mock_channel = AsyncMock(spec=discord.TextChannel)
    bot.get_channel = lambda cid: mock_channel if cid == ch_b else None

    result = await _send_to_teams(bot, ch_a, [team_b.name, "NONEXISTENT"], "Partial")

    mock_channel.send.assert_called_once()
    assert team_b.name in result.description
    # Should have Message field and Errors field
    field_values = {f.name: f.value for f in result.fields}
    assert "Message" in field_values
    assert "Errors" in field_values
    assert "not found" in field_values["Errors"]


# --- Deprecated prefix_msg ---


@pytest.fixture
def messaging_cog(bot):
    return Messaging(bot)


@pytest.mark.asyncio
async def test_prefix_msg_shows_deprecation(messaging_cog):
    ctx = MagicMock()
    ctx.send = AsyncMock()
    await messaging_cog.prefix_msg.callback(messaging_cog, ctx, "Team1", "hello")

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "replaced" in embed.description
