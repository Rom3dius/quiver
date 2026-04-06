"""Cog for handling team intel requests via !request and /request."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.embeds import error_embed, request_received_embed
from quiver.bot.utils import get_db_path, get_team_by_channel
from quiver.db.connection import get_connection
from quiver.services import request_service

logger = logging.getLogger("quiver.bot.intel_requests")


class IntelRequests(commands.Cog):
    """Handle intel requests from teams."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _handle_request(
        self, channel_id: int, message_id: str | None, content: str
    ) -> tuple[discord.Embed, bool]:
        """Shared logic for prefix and slash commands. Returns (embed, success)."""
        conn = get_connection(get_db_path(self.bot))
        try:
            team = get_team_by_channel(conn, channel_id)
            if team is None:
                return (
                    error_embed("This channel is not associated with any team."),
                    False,
                )

            request = request_service.create_request(
                conn,
                team_id=team.id,
                content=content,
                discord_message_id=message_id,
            )
            logger.info(
                "Intel request #%d from %s: %.80s",
                request.id,
                team.name,
                content,
            )
            return request_received_embed(request.id, content), True
        finally:
            conn.close()

    @commands.command(name="request", aliases=["req"])
    async def prefix_request(self, ctx: commands.Context, *, content: str) -> None:
        """Submit an intelligence request to Command & Control.

        Usage: !request <your request text>
        """
        embed, success = await self._handle_request(
            ctx.channel.id, str(ctx.message.id), content
        )
        await ctx.send(embed=embed)

    @app_commands.command(
        name="request", description="Submit an intelligence request to C2"
    )
    @app_commands.describe(content="Your intel request — what do you need?")
    async def slash_request(
        self, interaction: discord.Interaction, content: str
    ) -> None:
        embed, success = await self._handle_request(
            interaction.channel_id, None, content
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IntelRequests(bot))
