"""Tests for the messaging cog logic."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from quiver.bot.cogs.messaging import (
    Messaging,
    _send_to_teams,
    _validate_discord_attachment,
)
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


# --- Attachment validation ---


def _mock_attachment(
    filename: str = "report.pdf",
    size: int = 1024,
    content_type: str = "application/pdf",
) -> MagicMock:
    att = MagicMock(spec=discord.Attachment)
    att.filename = filename
    att.size = size
    att.content_type = content_type
    att.save = AsyncMock()
    return att


def test_validate_attachment_allowed():
    att = _mock_attachment("report.pdf", 1024)
    assert _validate_discord_attachment(att) is None


def test_validate_attachment_bad_extension():
    att = _mock_attachment("exploit.exe", 1024)
    error = _validate_discord_attachment(att)
    assert error is not None
    assert ".exe" in error


def test_validate_attachment_too_large():
    att = _mock_attachment("huge.png", 20 * 1024 * 1024)
    error = _validate_discord_attachment(att)
    assert error is not None
    assert "too large" in error.lower()


def test_validate_attachment_no_extension():
    att = _mock_attachment("Makefile", 100)
    # Path("Makefile").suffix is ""
    error = _validate_discord_attachment(att)
    assert error is not None
    assert "no extension" in error.lower()


# --- Sending with attachment ---


@pytest.mark.asyncio
async def test_send_with_attachment(bot, db_path, teams, tmp_path):
    team_b = teams[1]
    ch_a, ch_b, _ = _setup_teams(db_path, teams)

    mock_channel = AsyncMock(spec=discord.TextChannel)
    bot.get_channel = lambda cid: mock_channel if cid == ch_b else None

    # Mock the config uploads_path so attachment gets saved to tmp_path
    bot.quiver_config = MagicMock()
    bot.quiver_config.uploads_path = tmp_path

    att = _mock_attachment("intel.pdf", 2048, "application/pdf")

    # Make save() create a real file so _send_to_teams can read it
    async def fake_save(dest):
        Path(dest).write_bytes(b"fake pdf content")

    att.save = fake_save

    result = await _send_to_teams(bot, ch_a, [team_b.name], "See attached", att)

    # Message was sent with file
    call_kwargs = mock_channel.send.call_args[1]
    assert "file" in call_kwargs
    assert isinstance(call_kwargs["file"], discord.File)
    assert team_b.name in result.description

    # Attachment was recorded in DB
    from quiver.db.connection import get_connection as gc

    conn = gc(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM attachments WHERE message_id IS NOT NULL"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["filename"] == "intel.pdf"
    finally:
        conn.close()

    # Summary embed mentions the attachment
    field_names = [f.name for f in result.fields]
    assert "Attachment" in field_names


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
    assert "/msg" in embed.description
