"""Cog for the unified /menu and !menu command with button-based navigation."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.cogs.intel_requests import RequestModal
from quiver.bot.cogs.messaging import TeamSelectView
from quiver.bot.embeds import error_embed, teams_list_embed
from quiver.bot.utils import get_db_path, get_team_by_channel
from quiver.db.connection import get_connection
from quiver.repositories import team_repo

logger = logging.getLogger("quiver.bot.menu")

MENU_COLOUR = 0x9B59B6  # Purple, matches COLOUR_INFO


def _menu_embed() -> discord.Embed:
    return discord.Embed(
        title="Quiver Command Menu",
        description="Select an action below.",
        colour=MENU_COLOUR,
    )


class MenuView(discord.ui.View):
    """Persistent view with buttons for all primary bot actions."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="Intel Request", style=discord.ButtonStyle.primary, row=0)
    async def intel_request_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = get_connection(get_db_path(self.bot))
        try:
            team = get_team_by_channel(conn, interaction.channel_id)
        finally:
            conn.close()

        if team is None:
            await interaction.response.send_message(
                embed=error_embed("This channel is not associated with any team."),
                ephemeral=True,
            )
            return

        modal = RequestModal(self.bot, interaction.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Message Teams", style=discord.ButtonStyle.primary, row=0)
    async def message_teams_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = get_connection(get_db_path(self.bot))
        try:
            from_team = get_team_by_channel(conn, interaction.channel_id)
            if from_team is None:
                await interaction.response.send_message(
                    embed=error_embed("This channel is not associated with any team."),
                    ephemeral=True,
                )
                return

            teams = team_repo.get_all(conn)
        finally:
            conn.close()

        options = [
            discord.SelectOption(label=t.name, value=t.name)
            for t in teams
            if t.name != from_team.name
        ]

        if not options:
            await interaction.response.send_message(
                embed=error_embed("No other teams available to message."),
                ephemeral=True,
            )
            return

        view = TeamSelectView(self.bot, options, interaction.channel_id)
        await interaction.response.send_message(
            "Select the teams you want to message:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Teams", style=discord.ButtonStyle.secondary, row=1)
    async def teams_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        conn = get_connection(get_db_path(self.bot))
        try:
            teams = team_repo.get_all(conn)
        finally:
            conn.close()

        embed = teams_list_embed([t.name for t in teams])
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Menu(commands.Cog):
    """Unified command menu with button-based navigation."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _send_menu(self) -> tuple[discord.Embed, MenuView]:
        return _menu_embed(), MenuView(self.bot)

    @commands.command(name="menu")
    async def prefix_menu(self, ctx: commands.Context) -> None:
        """Open the command menu with interactive buttons."""
        embed, view = await self._send_menu()
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="menu", description="Open the command menu")
    async def slash_menu(self, interaction: discord.Interaction) -> None:
        embed, view = await self._send_menu()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Menu(bot))
