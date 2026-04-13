"""Discord bot entry point with cog loading and channel validation."""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from quiver.bot.embeds import error_embed
from quiver.config import Config
from quiver.db.connection import get_connection
from quiver.db.migrate import init_db
from quiver.repositories import event_repo, team_repo

logger = logging.getLogger("quiver.bot")


def create_bot(config: Config) -> commands.Bot:
    """Create and configure the Discord bot."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix=config.bot_command_prefix,
        intents=intents,
        help_command=_build_help_command(),
    )

    # Attach config to the bot instance so cogs can access it via self.bot
    # without needing globals or dependency injection frameworks.
    bot.quiver_config = config  # type: ignore[attr-defined]
    bot.quiver_db_path = config.database_path  # type: ignore[attr-defined]

    @bot.event
    async def on_ready() -> None:
        logger.info("Bot connected as %s (ID: %s)", bot.user, bot.user.id)
        _log_infra_event(
            config.database_path, "bot_connected", f"Connected as {bot.user}"
        )
        await _validate_team_channels(bot, config.database_path)

    @bot.event
    async def on_resumed() -> None:
        logger.info("Bot session resumed")
        _log_infra_event(
            config.database_path, "bot_reconnected", "Session resumed after disconnect"
        )

    @bot.event
    async def on_disconnect() -> None:
        logger.warning("Bot disconnected from Discord")

    @bot.event
    async def on_command_error(
        ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            cmd = ctx.invoked_with
            await ctx.send(
                embed=error_embed(
                    f"Unknown command `!{cmd}`. Use `!help` or `/help` to see available commands."
                )
            )
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=error_embed(
                    f"Missing argument: **{error.param.name}**. Use `!help {ctx.command}` for usage info."
                )
            )
            return
        logger.error("Command error in %s: %s", ctx.command, error, exc_info=error)
        await ctx.send(embed=error_embed("An error occurred processing your command."))

    return bot


async def load_cogs(bot: commands.Bot) -> None:
    """Load all bot cogs."""
    cog_modules = [
        "quiver.bot.cogs.intel_requests",
        "quiver.bot.cogs.messaging",
        "quiver.bot.cogs.inject_delivery",
        "quiver.bot.cogs.status",
        "quiver.bot.cogs.menu",
    ]
    for module in cog_modules:
        await bot.load_extension(module)
        logger.info("Loaded cog: %s", module)


async def _validate_team_channels(bot: commands.Bot, db_path: Path) -> None:
    """Check that all team Discord channels are accessible."""
    conn = get_connection(db_path)
    try:
        teams = team_repo.get_all(conn)
    finally:
        conn.close()

    valid = 0
    invalid = 0
    for team in teams:
        channel_id = team.discord_channel_id
        # Seed data uses PLACEHOLDER_ IDs; operators replace them before the game
        if channel_id.startswith("PLACEHOLDER_"):
            logger.warning(
                "Team '%s' has placeholder channel ID — update before game start",
                team.name,
            )
            invalid += 1
            continue

        # Try cache first, fall back to API (channel may not be cached yet)
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except Exception:
                channel = None

        if channel is None:
            logger.error(
                "Team '%s' channel ID %s not found — bot may lack access",
                team.name,
                channel_id,
            )
            invalid += 1
        else:
            valid += 1

    logger.info(
        "Channel validation: %d valid, %d invalid out of %d teams",
        valid,
        invalid,
        len(teams),
    )


def _log_infra_event(db_path: Path, event_type: str, details: str) -> None:
    """Log an infrastructure event to the game_events table."""
    try:
        conn = get_connection(db_path)
        try:
            event_repo.log(conn, event_type=event_type, details=details)
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to log infra event: %s", event_type)


def _build_help_command() -> commands.DefaultHelpCommand:
    return commands.DefaultHelpCommand(
        no_category="Quiver Commands",
    )


def run_bot(config: Config) -> None:
    """Initialize DB and start the bot."""
    conn = get_connection(config.database_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    bot = create_bot(config)

    @bot.event
    async def setup_hook() -> None:
        await load_cogs(bot)
        # Sync slash commands with Discord
        synced = await bot.tree.sync()
        logger.info("Synced %d slash commands", len(synced))

    bot.run(config.discord_token, log_level=logging.INFO)
