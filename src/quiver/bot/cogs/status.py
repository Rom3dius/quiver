"""Cog for !status, !teams and slash equivalents."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.embeds import error_embed, status_embed, teams_list_embed
from quiver.bot.utils import get_db_path, get_team_by_channel
from quiver.db.connection import get_connection
from quiver.repositories import team_repo

logger = logging.getLogger("quiver.bot.status")


class Status(commands.Cog):
    """Team status and info commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _handle_status(self, channel_id: int) -> discord.Embed:
        conn = get_connection(get_db_path(self.bot))
        try:
            team = get_team_by_channel(conn, channel_id)
            if team is None:
                return error_embed(
                    "This channel is not bound to any team. "
                    "Contact C2 if you believe this is an error."
                )
            return status_embed(team.name, channel_id)
        finally:
            conn.close()

    async def _handle_teams(self) -> discord.Embed:
        conn = get_connection(get_db_path(self.bot))
        try:
            teams = team_repo.get_all(conn)
            return teams_list_embed([t.name for t in teams])
        finally:
            conn.close()

    @commands.command(name="status")
    async def prefix_status(self, ctx: commands.Context) -> None:
        """Show your team's identity and available commands."""
        embed = await self._handle_status(ctx.channel.id)
        await ctx.send(embed=embed)

    @app_commands.command(
        name="status", description="Show your team identity and available commands"
    )
    async def slash_status(self, interaction: discord.Interaction) -> None:
        embed = await self._handle_status(interaction.channel_id)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="teams")
    async def prefix_teams(self, ctx: commands.Context) -> None:
        """List all teams in the wargame."""
        embed = await self._handle_teams()
        await ctx.send(embed=embed)

    @app_commands.command(name="teams", description="List all teams in the wargame")
    async def slash_teams(self, interaction: discord.Interaction) -> None:
        embed = await self._handle_teams()
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Status(bot))
