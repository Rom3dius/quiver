"""Background task cog that delivers pending injects and intel request responses."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands, tasks

from quiver.bot.embeds import inject_embed, request_response_embed
from quiver.bot.utils import bot_db, get_team_channel
from quiver.repositories import (
    attachment_repo,
    heartbeat_repo,
    inject_repo,
    request_repo,
    team_repo,
)
from quiver.services import inject_service, request_service

logger = logging.getLogger("quiver.bot.inject_delivery")


def _build_discord_files(attachments: list) -> list[discord.File]:
    """Convert attachment DB records to discord.File objects."""
    files = []
    for att in attachments:
        path = Path(att.stored_path)
        if path.exists():
            files.append(discord.File(str(path), filename=att.filename))
        else:
            logger.warning("Attachment file not found: %s", att.stored_path)
    return files


class InjectDelivery(commands.Cog):
    """Poll the database and deliver injects + responses to Discord."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.delivery_loop.start()

    def cog_unload(self) -> None:
        self.delivery_loop.cancel()

    # The bot polls the DB rather than receiving push notifications because
    # the web UI (Flask) and bot (discord.py) run in separate processes
    # and share state only through SQLite.  3 s is a balance between
    # responsiveness and DB load.
    @tasks.loop(seconds=3)
    async def delivery_loop(self) -> None:
        """Check for pending deliveries every 3 seconds."""
        try:
            self._write_heartbeat()
            await self._deliver_injects()
            await self._deliver_responses()
        except Exception:
            logger.exception("Error in delivery loop")

    def _write_heartbeat(self) -> None:
        # The dashboard reads this row to show bot online/offline status
        with bot_db(self.bot) as conn:
            guild_count = len(self.bot.guilds) if self.bot.guilds else 0
            heartbeat_repo.beat(conn, guild_count)

    @delivery_loop.before_loop
    async def before_delivery_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def _deliver_injects(self) -> None:
        with bot_db(self.bot) as conn:
            undelivered = inject_repo.get_undelivered_recipients(conn)
            if not undelivered:
                return

            for recipient in undelivered:
                team = team_repo.get_by_id(conn, recipient.team_id)
                if team is None:
                    logger.error(
                        "Team ID %d not found for recipient %d",
                        recipient.team_id,
                        recipient.id,
                    )
                    continue

                inj = inject_repo.get_by_id(conn, recipient.inject_id)
                if inj is None:
                    logger.error(
                        "Inject ID %d not found for recipient %d",
                        recipient.inject_id,
                        recipient.id,
                    )
                    continue

                channel = await get_team_channel(self.bot, team)
                if channel is None:
                    logger.error(
                        "Cannot deliver inject #%d to %s — channel not found",
                        inj.id,
                        team.name,
                    )
                    continue

                try:
                    async with channel.typing():
                        await asyncio.sleep(1)

                    attachments = attachment_repo.get_for_inject(conn, inj.id)
                    files = _build_discord_files(attachments)
                    embed = inject_embed(inj.content, inj.sent_by_operator)

                    await channel.send(embed=embed, files=files)
                    inject_service.mark_delivered(conn, recipient)
                    logger.info(
                        "Delivered inject #%d to %s (%d files)",
                        inj.id,
                        team.name,
                        len(files),
                    )
                except Exception:
                    logger.exception(
                        "Failed to deliver inject #%d to %s", inj.id, team.name
                    )

    async def _deliver_responses(self) -> None:
        with bot_db(self.bot) as conn:
            undelivered = request_repo.get_undelivered_responses(conn)
            if not undelivered:
                return

            for req in undelivered:
                team = team_repo.get_by_id(conn, req.team_id)
                if team is None:
                    logger.error(
                        "Team ID %d not found for request %d", req.team_id, req.id
                    )
                    continue

                channel = await get_team_channel(self.bot, team)
                if channel is None:
                    logger.error(
                        "Cannot deliver response for request #%d to %s",
                        req.id,
                        team.name,
                    )
                    continue

                try:
                    async with channel.typing():
                        await asyncio.sleep(1)

                    attachments = attachment_repo.get_for_request(conn, req.id)
                    files = _build_discord_files(attachments)
                    embed = request_response_embed(
                        req.status,
                        req.content,
                        req.response,
                    )

                    await channel.send(embed=embed, files=files)
                    request_service.mark_response_delivered(conn, req.id)
                    logger.info(
                        "Delivered %s response for request #%d to %s (%d files)",
                        req.status,
                        req.id,
                        team.name,
                        len(files),
                    )
                except Exception:
                    logger.exception(
                        "Failed to deliver response for request #%d to %s",
                        req.id,
                        team.name,
                    )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InjectDelivery(bot))
