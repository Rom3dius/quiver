"""Cog for inter-team messaging via !msg and /msg (supports multiple recipients)."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.embeds import error_embed, inter_team_message_embed, message_sent_embed
from quiver.bot.utils import (
    get_db_path,
    get_team_by_channel,
    get_team_channel,
    resolve_team_by_name,
)
from quiver.db.connection import get_connection
from quiver.repositories import team_repo
from quiver.services import message_service

logger = logging.getLogger("quiver.bot.messaging")


class ComposeModal(discord.ui.Modal, title="Compose Message"):
    """Modal for typing the message body after teams are selected.

    Step 2 of the /msg flow -- invoked by TeamSelect.callback.
    """

    message_input = discord.ui.TextInput(
        label="Message",
        placeholder="Type your message here...",
        style=discord.TextStyle.paragraph,
        required=True,
    )

    def __init__(
        self, bot: commands.Bot, selected_team_names: list[str], channel_id: int
    ) -> None:
        super().__init__()
        self.bot = bot
        self.selected_team_names = selected_team_names
        self.source_channel_id = channel_id
        # Show who they're sending to in the modal title
        names_preview = ", ".join(selected_team_names)
        if len(names_preview) > 30:
            names_preview = names_preview[:27] + "..."
        self.title = f"Message to {names_preview}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        result = await _send_to_teams(
            self.bot,
            self.source_channel_id,
            self.selected_team_names,
            self.message_input.value,
        )
        await interaction.response.send_message(embed=result)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        logger.exception("Modal error: %s", error)
        await interaction.response.send_message(
            embed=error_embed("Something went wrong sending your message."),
            ephemeral=True,
        )


class TeamSelect(discord.ui.Select):
    """Multi-select dropdown of teams (step 1 of the /msg flow)."""

    def __init__(
        self, bot: commands.Bot, options: list[discord.SelectOption], channel_id: int
    ) -> None:
        super().__init__(
            placeholder="Select recipient teams...",
            min_values=1,
            max_values=len(options),
            options=options,
        )
        self.bot = bot
        self.source_channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        modal = ComposeModal(self.bot, self.values, self.source_channel_id)
        await interaction.response.send_modal(modal)


class TeamSelectView(discord.ui.View):
    """Ephemeral view containing the team multi-select."""

    def __init__(
        self, bot: commands.Bot, options: list[discord.SelectOption], channel_id: int
    ) -> None:
        super().__init__(timeout=120)
        self.add_item(TeamSelect(bot, options, channel_id))


class Messaging(commands.Cog):
    """Handle inter-team communication."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="msg", aliases=["message"])
    async def prefix_msg(
        self, ctx: commands.Context, target_teams_str: str, *, content: str
    ) -> None:
        """Send a message to one or more teams.

        Usage: !msg <Team1,Team2,...> <message>
        Examples:
          !msg CIA We have intel to share
          !msg CIA,MI6 Joint operation briefing
        """
        team_names = [n.strip() for n in target_teams_str.split(",") if n.strip()]
        result = await _send_to_teams(self.bot, ctx.channel.id, team_names, content)
        await ctx.send(embed=result)

    # Two-step slash flow: first show an ephemeral team selector dropdown,
    # then open a modal for the message body.  This avoids requiring the
    # user to type team names manually in a slash command argument.
    @app_commands.command(name="msg", description="Send a message to one or more teams")
    async def slash_msg(self, interaction: discord.Interaction) -> None:
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


async def _send_to_teams(
    bot: commands.Bot,
    channel_id: int,
    target_team_names: list[str],
    content: str,
) -> discord.Embed:
    """Send a message to multiple teams. Returns a summary embed."""
    conn = get_connection(get_db_path(bot))
    try:
        from_team = get_team_by_channel(conn, channel_id)
        if from_team is None:
            return error_embed("This channel is not associated with any team.")

        sent_to: list[str] = []
        errors: list[str] = []

        for name in target_team_names:
            to_team = resolve_team_by_name(conn, name)
            if to_team is None:
                errors.append(f"'{name}' not found")
                continue

            if to_team.id == from_team.id:
                errors.append("cannot message your own team")
                continue

            target_channel = await get_team_channel(bot, to_team)
            if target_channel is None:
                errors.append(f"cannot reach {to_team.name}'s channel")
                continue

            message_service.send_message(conn, from_team.id, to_team.id, content)
            embed = inter_team_message_embed(from_team.name, content)
            await target_channel.send(embed=embed)
            sent_to.append(to_team.name)

            logger.info(
                "Inter-team message: %s -> %s: %.80s",
                from_team.name,
                to_team.name,
                content,
            )

        # Partial success: report what succeeded and what failed separately
        if sent_to and not errors:
            return message_sent_embed(sent_to, content)

        if sent_to and errors:
            result = message_sent_embed(sent_to, content)
            result.add_field(
                name="Errors",
                value="\n".join(f"\u26a0\ufe0f {e}" for e in errors),
                inline=False,
            )
            return result

        return error_embed(
            "Could not send to any team:\n"
            + "\n".join(f"\u2022 {e}" for e in errors)
            + "\n\nUse `!teams` or `/teams` to see available teams."
        )
    finally:
        conn.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Messaging(bot))
