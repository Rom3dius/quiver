"""Tests for the intel_requests cog logic."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.intel_requests import (
    IntelRequests,
    RequestModal,
    _handle_request,
)
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


def _make_interaction(channel_id: int) -> MagicMock:
    interaction = MagicMock()
    interaction.channel_id = channel_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


# --- _handle_request tests (module-level function) ---


@pytest.mark.asyncio
async def test_handle_request_creates_request(bot, db_path, teams):
    first_team = teams[0]
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, first_team.name)
        team_repo.update_channel_id(conn, team.id, "99999")
    finally:
        conn.close()

    embed, success = await _handle_request(
        bot, 99999, "12345", "Need satellite imagery of Berlin"
    )

    assert success is True
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
async def test_handle_request_unknown_channel(bot, db_path):
    embed, success = await _handle_request(bot, 11111, None, "Some request")
    assert success is False
    assert "not associated" in embed.description


@pytest.mark.asyncio
async def test_handle_request_empty_content(bot, db_path):
    embed, success = await _handle_request(bot, 99999, None, "   ")
    assert success is False
    assert "cannot be empty" in embed.description


# --- slash_request tests (opens modal) ---


@pytest.mark.asyncio
async def test_slash_request_opens_modal_for_known_team(cog, db_path, teams):
    first_team = teams[0]
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, first_team.name)
        team_repo.update_channel_id(conn, team.id, "99999")
    finally:
        conn.close()

    interaction = _make_interaction(channel_id=99999)
    await cog.slash_request.callback(cog, interaction)

    interaction.response.send_modal.assert_called_once()
    modal = interaction.response.send_modal.call_args[0][0]
    assert isinstance(modal, RequestModal)


@pytest.mark.asyncio
async def test_slash_request_rejects_unknown_channel(cog, db_path):
    interaction = _make_interaction(channel_id=11111)
    await cog.slash_request.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args[1]["embed"]
    assert "not associated" in embed.description


# --- RequestModal.on_submit tests ---


@pytest.mark.asyncio
async def test_request_modal_on_submit_creates_request(bot, db_path, teams):
    first_team = teams[0]
    conn = get_connection(db_path)
    try:
        team = team_repo.get_by_name(conn, first_team.name)
        team_repo.update_channel_id(conn, team.id, "99999")
    finally:
        conn.close()

    modal = RequestModal(bot, channel_id=99999)
    modal.content_input._value = "Need satellite imagery of Berlin"

    interaction = _make_interaction(channel_id=99999)
    await modal.on_submit(interaction)

    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args[1]["embed"]
    assert "Intel Request Submitted" in embed.title

    check_conn = get_connection(db_path)
    try:
        pending = request_repo.get_pending(check_conn)
        assert len(pending) == 1
        assert "satellite imagery" in pending[0].content
    finally:
        check_conn.close()


# --- Deprecated prefix_request ---


@pytest.mark.asyncio
async def test_prefix_request_shows_deprecation(cog):
    ctx = _make_ctx(channel_id=99999)
    await cog.prefix_request.callback(cog, ctx, content="Some request")

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "replaced" in embed.description
