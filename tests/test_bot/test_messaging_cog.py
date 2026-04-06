"""Tests for the messaging cog logic."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.messaging import _send_to_teams
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


def _setup_teams(db_path: str) -> tuple[int, int, int]:
    conn = get_connection(db_path)
    try:
        cia = team_repo.get_by_name(conn, "CIA")
        mi6 = team_repo.get_by_name(conn, "MI6")
        bnd = team_repo.get_by_name(conn, "BND")
        team_repo.update_channel_id(conn, cia.id, "100")
        team_repo.update_channel_id(conn, mi6.id, "200")
        team_repo.update_channel_id(conn, bnd.id, "300")
    finally:
        conn.close()
    return 100, 200, 300


@pytest.mark.asyncio
async def test_send_single_team(bot, db_path):
    cia_ch, mi6_ch, _ = _setup_teams(db_path)

    mock_channel = AsyncMock(spec=discord.TextChannel)
    bot.get_channel = lambda cid: mock_channel if cid == mi6_ch else None

    result = await _send_to_teams(bot, cia_ch, ["MI6"], "Intel to share")

    mock_channel.send.assert_called_once()
    assert "MI6" in result.description


@pytest.mark.asyncio
async def test_send_multiple_teams(bot, db_path):
    cia_ch, mi6_ch, bnd_ch = _setup_teams(db_path)

    channels = {
        mi6_ch: AsyncMock(spec=discord.TextChannel),
        bnd_ch: AsyncMock(spec=discord.TextChannel),
    }
    bot.get_channel = lambda cid: channels.get(cid)

    result = await _send_to_teams(bot, cia_ch, ["MI6", "BND"], "Joint briefing")

    channels[mi6_ch].send.assert_called_once()
    channels[bnd_ch].send.assert_called_once()
    assert "MI6" in result.description
    assert "BND" in result.description


@pytest.mark.asyncio
async def test_send_unknown_target(bot, db_path):
    _setup_teams(db_path)

    result = await _send_to_teams(bot, 100, ["NONEXISTENT"], "Hello")
    assert "not found" in result.description


@pytest.mark.asyncio
async def test_send_to_self(bot, db_path):
    _setup_teams(db_path)

    result = await _send_to_teams(bot, 100, ["CIA"], "Talking to myself")
    assert "own team" in result.description


@pytest.mark.asyncio
async def test_partial_failure(bot, db_path):
    cia_ch, mi6_ch, _ = _setup_teams(db_path)

    mock_channel = AsyncMock(spec=discord.TextChannel)
    bot.get_channel = lambda cid: mock_channel if cid == mi6_ch else None

    result = await _send_to_teams(bot, cia_ch, ["MI6", "NONEXISTENT"], "Partial")

    mock_channel.send.assert_called_once()
    assert "MI6" in result.description
    # Should have Message field and Errors field
    field_values = {f.name: f.value for f in result.fields}
    assert "Message" in field_values
    assert "Errors" in field_values
    assert "not found" in field_values["Errors"]
