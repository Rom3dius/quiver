"""Tests for the intel_requests cog logic."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.intel_requests import IntelRequests
from quiver.db.connection import get_connection
from quiver.repositories import request_repo, team_repo


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
    return IntelRequests(bot)


def _make_ctx(channel_id: int, message_id: int = 12345) -> MagicMock:
    ctx = MagicMock()
    ctx.channel.id = channel_id
    ctx.message.id = message_id
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_submit_request_from_known_team(cog, db_path):
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, "CIA")
        team_repo.update_channel_id(conn, team.id, "99999")
    finally:
        conn.close()

    ctx = _make_ctx(channel_id=99999)
    await cog.prefix_request.callback(
        cog, ctx, content="Need satellite imagery of Berlin"
    )

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert isinstance(embed, discord.Embed)
    assert "Intel Request Submitted" in embed.title

    check_conn = get_connection(db_path)
    try:
        pending = request_repo.get_pending(check_conn)
        assert len(pending) == 1
        assert "satellite imagery" in pending[0].content
    finally:
        check_conn.close()


@pytest.mark.asyncio
async def test_submit_request_from_unknown_channel(cog, db_path):
    ctx = _make_ctx(channel_id=11111)
    await cog.prefix_request.callback(cog, ctx, content="Some request")

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "not associated" in embed.description
