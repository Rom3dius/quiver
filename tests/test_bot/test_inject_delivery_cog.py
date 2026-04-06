"""Tests for the inject delivery background loop logic."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.inject_delivery import InjectDelivery
from quiver.db.connection import get_connection
from quiver.repositories import inject_repo, request_repo, team_repo
from quiver.services import inject_service, request_service


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
    mock_bot.wait_until_ready = AsyncMock()
    return mock_bot


@pytest.fixture
def cog(bot):
    cog = InjectDelivery.__new__(InjectDelivery)
    cog.bot = bot
    return cog


def _setup_team(db_path: str, team_name: str, channel_id: str) -> None:
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, team_name)
        team_repo.update_channel_id(conn, team.id, channel_id)
    finally:
        conn.close()


def _make_mock_channel(channel_id: int):
    """Create a mock TextChannel that supports async context manager for typing()."""
    mock_channel = AsyncMock(spec=discord.TextChannel)

    @asynccontextmanager
    async def mock_typing():
        yield

    mock_channel.typing = mock_typing
    return mock_channel


@pytest.mark.asyncio
async def test_deliver_injects(cog, bot, db_path, teams):
    first_team = teams[0]
    _setup_team(db_path, first_team.name, "100")

    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, first_team.name)
        inject_service.send_inject(conn, "Flash report: target located", [team.id])
    finally:
        conn.close()

    mock_channel = _make_mock_channel(100)
    bot.get_channel = lambda cid: mock_channel if cid == 100 else None

    await cog._deliver_injects()

    mock_channel.send.assert_called_once()
    kwargs = mock_channel.send.call_args[1]
    assert isinstance(kwargs["embed"], discord.Embed)
    assert "Flash report" in kwargs["embed"].description

    conn = get_connection(db_path)
    try:
        undelivered = inject_repo.get_undelivered_recipients(conn)
        assert len(undelivered) == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_deliver_responses(cog, bot, db_path, teams):
    second_team = teams[1]
    _setup_team(db_path, second_team.name, "200")

    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, second_team.name)
        req = request_service.create_request(conn, team.id, "Need HUMINT on target")
        request_service.resolve_request(
            conn, req.id, "approved", "Agent meeting confirmed for 0800Z"
        )
    finally:
        conn.close()

    mock_channel = _make_mock_channel(200)
    bot.get_channel = lambda cid: mock_channel if cid == 200 else None

    await cog._deliver_responses()

    mock_channel.send.assert_called_once()
    kwargs = mock_channel.send.call_args[1]
    embed = kwargs["embed"]
    assert "APPROVED" in embed.title
    field_values = [f.value for f in embed.fields]
    assert any("Agent meeting confirmed" in v for v in field_values)

    conn = get_connection(db_path)
    try:
        undelivered = request_repo.get_undelivered_responses(conn)
        assert len(undelivered) == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_no_pending_deliveries(cog, bot, db_path):
    await cog._deliver_injects()
    await cog._deliver_responses()
