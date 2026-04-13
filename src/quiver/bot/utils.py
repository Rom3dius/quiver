"""Bot utility functions for channel and team resolution."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from typing import Generator

import discord
from discord.ext import commands

from quiver.db.connection import get_connection
from quiver.db.models import Team
from quiver.repositories import team_repo

logger = logging.getLogger("quiver.bot")

# Common error messages used across multiple cogs
ERR_NO_TEAM = "This channel is not associated with any team."
ERR_NO_TEAMS_TO_MSG = "No other teams available to message."


def get_db_path(bot: commands.Bot) -> str:
    """Get the database path stored on the bot instance."""
    return str(bot.quiver_db_path)  # type: ignore[attr-defined]


@contextmanager
def bot_db(bot: commands.Bot) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for bot cog database access."""
    conn = get_connection(get_db_path(bot))
    try:
        yield conn
    finally:
        conn.close()


def get_team_by_channel(conn: sqlite3.Connection, channel_id: int) -> Team | None:
    """Look up a team by the Discord channel ID of the message."""
    return team_repo.get_by_channel_id(conn, str(channel_id))


def resolve_team_by_name(conn: sqlite3.Connection, name: str) -> Team | None:
    """Resolve a team by name (case-insensitive)."""
    return team_repo.get_by_name(conn, name)


async def get_team_channel(bot: commands.Bot, team: Team) -> discord.TextChannel | None:
    """Get the Discord channel object for a team, falling back to API fetch."""
    try:
        channel_id = int(team.discord_channel_id)
    except ValueError:
        logger.error(
            "Invalid channel ID for team '%s': %s", team.name, team.discord_channel_id
        )
        return None

    channel = bot.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel

    # Cache miss — try fetching from API
    try:
        channel = await bot.fetch_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
    except (discord.NotFound, discord.Forbidden):
        logger.error("Cannot access channel %s for team '%s'", channel_id, team.name)
    except Exception:
        logger.exception(
            "Error fetching channel %s for team '%s'", channel_id, team.name
        )

    return None
