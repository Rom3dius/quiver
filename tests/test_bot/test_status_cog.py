"""Tests for the status cog."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.status import Status
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


@pytest.fixture
def cog(bot):
    return Status(bot)


def _make_ctx(channel_id: int) -> MagicMock:
    ctx = MagicMock()
    ctx.channel.id = channel_id
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_status_known_team(cog, db_path):
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, "CIA")
        team_repo.update_channel_id(conn, team.id, "100")
    finally:
        conn.close()

    ctx = _make_ctx(channel_id=100)
    await cog.prefix_status.callback(cog, ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert isinstance(embed, discord.Embed)
    assert "CIA" in embed.title


@pytest.mark.asyncio
async def test_status_unknown_channel(cog, db_path):
    ctx = _make_ctx(channel_id=99999)
    await cog.prefix_status.callback(cog, ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "not bound" in embed.description


@pytest.mark.asyncio
async def test_list_teams(cog, db_path):
    ctx = _make_ctx(channel_id=100)
    await cog.prefix_teams.callback(cog, ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "4" in embed.title
    assert "CIA" in embed.description
