"""Cog for handling team intel requests via !request and /request."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.embeds import error_embed, request_received_embed
from quiver.bot.utils import ERR_NO_TEAM, bot_db, get_team_by_channel
from quiver.services import request_service
from quiver.validation import MAX_REQUEST_CONTENT

logger = logging.getLogger("quiver.bot.intel_requests")


async def _handle_request(
    bot: commands.Bot, channel_id: int, message_id: str | None, content: str
) -> tuple[discord.Embed, bool]:
    """Shared logic for modal and slash flows. Returns (embed, success)."""
    if not content.strip():
        return error_embed("Request content cannot be empty."), False

    if len(content) > MAX_REQUEST_CONTENT:
        return (
            error_embed(
                f"Request too long ({len(content)} chars, "
                f"max {MAX_REQUEST_CONTENT})."
            ),
            False,
        )

    with bot_db(bot) as conn:
        team = get_team_by_channel(conn, channel_id)
        if team is None:
            return error_embed(ERR_NO_TEAM), False

        req = request_service.create_request(
            conn,
            team_id=team.id,
            content=content,
            discord_message_id=message_id,
        )
        logger.info(
            "Intel request #%d from %s: %.80s",
            req.id,
            team.name,
            content,
        )
        return request_received_embed(req.id, content), True


class RequestModal(discord.ui.Modal, title="Submit Intel Request"):
    """Modal for composing an intel request to C2."""

    content_input = discord.ui.TextInput(
        label="Intel Request",
        placeholder="What intelligence do you need from C2?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=MAX_REQUEST_CONTENT,
    )

    def __init__(self, bot: commands.Bot, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.source_channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed, _success = await _handle_request(
            self.bot, self.source_channel_id, None, self.content_input.value
        )
        await interaction.response.send_message(embed=embed)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        logger.exception("RequestModal error: %s", error)
        await interaction.response.send_message(
            embed=error_embed("Something went wrong submitting your request."),
            ephemeral=True,
        )


class IntelRequests(commands.Cog):
    """Handle intel requests from teams."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="request", aliases=["req"])
    async def prefix_request(self, ctx: commands.Context, *, content: str = "") -> None:
        """Submit an intel request — opens the request modal."""
        await ctx.send(
            embed=error_embed("Use `/request` or `/menu` to submit intel requests.")
        )

    @app_commands.command(
        name="request", description="Submit an intelligence request to C2"
    )
    async def slash_request(
        self,
        interaction: discord.Interaction,
    ) -> None:
        with bot_db(self.bot) as conn:
            team = get_team_by_channel(conn, interaction.channel_id)

        if team is None:
            await interaction.response.send_message(
                embed=error_embed(ERR_NO_TEAM),
                ephemeral=True,
            )
            return

        modal = RequestModal(self.bot, interaction.channel_id)
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IntelRequests(bot))
