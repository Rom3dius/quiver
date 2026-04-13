"""Tests for the status cog."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.status import Status


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
    mock_bot.quiver_config = MagicMock()
    mock_bot.quiver_config.admin_role_name = "C2 Operator"
    return mock_bot


@pytest.fixture
def cog(bot):
    return Status(bot)


def _make_ctx(channel_id: int) -> MagicMock:
    ctx = MagicMock()
    ctx.channel.id = channel_id
    ctx.send = AsyncMock()
    return ctx


def _make_interaction(
    *, has_role: bool = True, role_name: str = "C2 Operator"
) -> MagicMock:
    interaction = MagicMock()
    interaction.channel_id = 99999
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_role = MagicMock()
    mock_role.name = role_name
    interaction.user = MagicMock()
    interaction.user.roles = [mock_role] if has_role else []
    return interaction


# --- /status admin command ---


@pytest.mark.asyncio
async def test_slash_status_with_admin_role(cog, db_path, teams):
    interaction = _make_interaction(has_role=True)
    await cog.slash_status.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args[1]
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert "Game Status" in embed.title


@pytest.mark.asyncio
async def test_slash_status_without_admin_role(cog, db_path):
    interaction = _make_interaction(has_role=False)
    await cog.slash_status.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args[1]
    embed = kwargs["embed"]
    assert "C2 Operator" in embed.description
    assert kwargs["ephemeral"] is True


# --- Deprecated !status ---


@pytest.mark.asyncio
async def test_prefix_status_shows_deprecation(cog):
    ctx = _make_ctx(channel_id=99999)
    await cog.prefix_status.callback(cog, ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "/status" in embed.description


# --- /teams (unchanged) ---


@pytest.mark.asyncio
async def test_list_teams(cog, db_path, teams):
    ctx = _make_ctx(channel_id=100)
    await cog.prefix_teams.callback(cog, ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert str(len(teams)) in embed.title
    for team in teams:
        assert team.name in embed.description
