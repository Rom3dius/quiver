"""Tests for the menu cog."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.intel_requests import RequestModal
from quiver.bot.cogs.menu import Menu, MenuView
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
    return Menu(bot)


def _make_ctx(channel_id: int) -> MagicMock:
    ctx = MagicMock()
    ctx.channel.id = channel_id
    ctx.send = AsyncMock()
    return ctx


def _make_interaction(channel_id: int) -> MagicMock:
    interaction = MagicMock()
    interaction.channel_id = channel_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


# --- Menu command tests ---


@pytest.mark.asyncio
async def test_prefix_menu_sends_view_with_buttons(cog):
    ctx = _make_ctx(channel_id=99999)
    await cog.prefix_menu.callback(cog, ctx)

    ctx.send.assert_called_once()
    kwargs = ctx.send.call_args[1]
    assert isinstance(kwargs["embed"], discord.Embed)
    assert "Command Menu" in kwargs["embed"].title

    view = kwargs["view"]
    assert isinstance(view, MenuView)
    # Should have 4 buttons (2 primary + 2 secondary)
    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
    assert len(buttons) == 3


@pytest.mark.asyncio
async def test_slash_menu_sends_view(cog):
    interaction = _make_interaction(channel_id=99999)
    await cog.slash_menu.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args[1]
    assert isinstance(kwargs["embed"], discord.Embed)
    assert isinstance(kwargs["view"], MenuView)


# --- Button callback tests ---


@pytest.mark.asyncio
async def test_intel_request_button_opens_modal(bot, db_path, teams):
    first_team = teams[0]
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, first_team.name)
        team_repo.update_channel_id(conn, team.id, "99999")
    finally:
        conn.close()

    view = MenuView(bot)
    interaction = _make_interaction(channel_id=99999)

    # Find the intel request button and call it
    btn = next(
        c
        for c in view.children
        if isinstance(c, discord.ui.Button) and c.label == "Intel Request"
    )
    await btn.callback(interaction)

    interaction.response.send_modal.assert_called_once()
    modal = interaction.response.send_modal.call_args[0][0]
    assert isinstance(modal, RequestModal)


@pytest.mark.asyncio
async def test_intel_request_button_rejects_unknown_channel(bot, db_path):
    view = MenuView(bot)
    interaction = _make_interaction(channel_id=11111)

    btn = next(
        c
        for c in view.children
        if isinstance(c, discord.ui.Button) and c.label == "Intel Request"
    )
    await btn.callback(interaction)

    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args[1]["embed"]
    assert "not associated" in embed.description


@pytest.mark.asyncio
async def test_teams_button_shows_teams(bot, db_path, teams):
    view = MenuView(bot)
    interaction = _make_interaction(channel_id=99999)

    btn = next(
        c
        for c in view.children
        if isinstance(c, discord.ui.Button) and c.label == "Teams"
    )
    await btn.callback(interaction)

    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args[1]["embed"]
    assert "Teams" in embed.title
