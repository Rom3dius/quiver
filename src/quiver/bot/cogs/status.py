"""Cog for /status (admin stats), /teams, and prefix equivalents."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.embeds import admin_status_embed, error_embed, teams_list_embed
from quiver.bot.utils import get_db_path
from quiver.db.connection import get_connection
from quiver.repositories import (
    heartbeat_repo,
    inject_repo,
    message_repo,
    request_repo,
    team_repo,
)

logger = logging.getLogger("quiver.bot.status")


class Status(commands.Cog):
    """Admin status dashboard and team list commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _get_admin_role_name(self) -> str:
        config = getattr(self.bot, "quiver_config", None)
        if config is not None:
            return config.admin_role_name
        return "C2 Operator"

    async def _handle_teams(self) -> discord.Embed:
        conn = get_connection(get_db_path(self.bot))
        try:
            teams = team_repo.get_all(conn)
            return teams_list_embed([t.name for t in teams])
        finally:
            conn.close()

    async def _build_status_embed(self) -> discord.Embed:
        conn = get_connection(get_db_path(self.bot))
        try:
            # Bot heartbeat
            heartbeat = heartbeat_repo.get(conn)
            if heartbeat is None:
                bot_online = False
                bot_age = None
                guild_count = 0
            else:
                now = datetime.now(timezone.utc)
                last_beat_utc = heartbeat.last_beat.replace(tzinfo=timezone.utc)
                age = (now - last_beat_utc).total_seconds()
                bot_online = age < 15
                bot_age = round(age)
                guild_count = heartbeat.guild_count

            team_count = len(team_repo.get_all(conn))
            inject_total = inject_repo.count(conn)
            inject_pending = len(inject_repo.get_undelivered_recipients(conn))
            req_summary = request_repo.request_summary(conn)
            msg_count = message_repo.count(conn)
        finally:
            conn.close()

        return admin_status_embed(
            bot_online=bot_online,
            bot_age_seconds=bot_age,
            guild_count=guild_count,
            team_count=team_count,
            inject_total=inject_total,
            inject_pending=inject_pending,
            request_summary=req_summary,
            message_count=msg_count,
        )

    # --- /status (admin only) ---

    @app_commands.command(
        name="status", description="Show game status dashboard (admin only)"
    )
    async def slash_status(self, interaction: discord.Interaction) -> None:
        role_name = self._get_admin_role_name()
        member = interaction.user
        if not any(r.name == role_name for r in getattr(member, "roles", [])):
            await interaction.response.send_message(
                embed=error_embed(
                    f"You need the **{role_name}** role to use this command."
                ),
                ephemeral=True,
            )
            return

        embed = await self._build_status_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="status")
    async def prefix_status(self, ctx: commands.Context) -> None:
        """Deprecated — use /status instead."""
        await ctx.send(
            embed=error_embed(
                "The `!status` command has been replaced.\n"
                "Please use `/status` instead (admin only)."
            )
        )

    # --- /teams (available to everyone) ---

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
