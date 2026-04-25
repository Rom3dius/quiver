"""Cog for inter-team messaging via !msg and /msg (supports multiple recipients)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from quiver.bot.embeds import error_embed, inter_team_message_embed, message_sent_embed
from quiver.bot.utils import (
    ERR_NO_TEAM,
    ERR_NO_TEAMS_TO_MSG,
    bot_db,
    get_team_by_channel,
    get_team_channel,
    resolve_team_by_name,
)
from quiver.repositories import attachment_repo, team_repo
from quiver.services import message_service
from quiver.validation import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MAX_MESSAGE_CONTENT,
    infer_content_type,
)

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
        max_length=MAX_MESSAGE_CONTENT,
    )

    def __init__(
        self,
        bot: commands.Bot,
        selected_team_names: list[str],
        channel_id: int,
        attachment: discord.Attachment | None = None,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.selected_team_names = selected_team_names
        self.source_channel_id = channel_id
        self.attachment = attachment
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
            self.attachment,
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
        self,
        bot: commands.Bot,
        options: list[discord.SelectOption],
        channel_id: int,
        attachment: discord.Attachment | None = None,
    ) -> None:
        super().__init__(
            placeholder="Select recipient teams...",
            min_values=1,
            max_values=len(options),
            options=options,
        )
        self.bot = bot
        self.source_channel_id = channel_id
        self.attachment = attachment

    async def callback(self, interaction: discord.Interaction) -> None:
        modal = ComposeModal(
            self.bot, self.values, self.source_channel_id, self.attachment
        )
        await interaction.response.send_modal(modal)


class TeamSelectView(discord.ui.View):
    """Ephemeral view containing the team multi-select."""

    def __init__(
        self,
        bot: commands.Bot,
        options: list[discord.SelectOption],
        channel_id: int,
        attachment: discord.Attachment | None = None,
    ) -> None:
        super().__init__(timeout=120)
        self.add_item(TeamSelect(bot, options, channel_id, attachment))


class Messaging(commands.Cog):
    """Handle inter-team communication."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="msg", aliases=["message"])
    async def prefix_msg(self, ctx: commands.Context, *args: str) -> None:
        """Send a message to other teams — use the slash command."""
        await ctx.send(
            embed=error_embed("Use `/msg` or `/menu` to send inter-team messages.")
        )

    # Two-step slash flow: first show an ephemeral team selector dropdown,
    # then open a modal for the message body.  This avoids requiring the
    # user to type team names manually in a slash command argument.
    @app_commands.command(name="msg", description="Send a message to one or more teams")
    @app_commands.describe(attachment="Optional file to attach to the message")
    async def slash_msg(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment | None = None,
    ) -> None:
        # Validate attachment early so the user doesn't fill out the
        # whole form only to get an error at send time.
        if attachment is not None:
            error = _validate_discord_attachment(attachment)
            if error is not None:
                await interaction.response.send_message(
                    embed=error_embed(error), ephemeral=True
                )
                return

        with bot_db(self.bot) as conn:
            from_team = get_team_by_channel(conn, interaction.channel_id)
            if from_team is None:
                await interaction.response.send_message(
                    embed=error_embed(ERR_NO_TEAM),
                    ephemeral=True,
                )
                return

            teams = team_repo.get_all(conn)

        options = [
            discord.SelectOption(label=t.name, value=t.name)
            for t in teams
            if t.name != from_team.name
        ]

        if not options:
            await interaction.response.send_message(
                embed=error_embed(ERR_NO_TEAMS_TO_MSG),
                ephemeral=True,
            )
            return

        prompt = "Select the teams you want to message:"
        if attachment is not None:
            prompt += f"\n📎 Attached: **{attachment.filename}**"

        view = TeamSelectView(self.bot, options, interaction.channel_id, attachment)
        await interaction.response.send_message(
            prompt,
            view=view,
            ephemeral=True,
        )


def _validate_discord_attachment(attachment: discord.Attachment) -> str | None:
    """Return an error message if the attachment is not allowed, else None."""
    suffix = Path(attachment.filename).suffix.lower()
    if not suffix:
        return "Attached file has no extension."
    if suffix not in ALLOWED_EXTENSIONS:
        return f"File type '{suffix}' is not permitted."
    if attachment.size > MAX_FILE_SIZE_BYTES:
        size_mb = attachment.size // (1024 * 1024)
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        return f"File too large ({size_mb} MB, max {max_mb} MB)."
    return None


async def _save_discord_attachment(
    bot: commands.Bot, attachment: discord.Attachment
) -> Path:
    """Download a Discord attachment to the uploads directory.

    Returns the on-disk path.
    """
    uploads_path: Path = bot.quiver_config.uploads_path  # type: ignore[attr-defined]
    unique_name = f"{uuid.uuid4().hex[:12]}_{attachment.filename}"
    dest = uploads_path / unique_name
    await attachment.save(dest)
    return dest


async def _send_to_teams(
    bot: commands.Bot,
    channel_id: int,
    target_team_names: list[str],
    content: str,
    attachment: discord.Attachment | None = None,
) -> discord.Embed:
    """Send a message to multiple teams. Returns a summary embed."""
    if not content.strip():
        return error_embed("Message content cannot be empty.")

    if len(content) > MAX_MESSAGE_CONTENT:
        return error_embed(
            f"Message too long ({len(content)} chars, max {MAX_MESSAGE_CONTENT})."
        )

    # Download the attachment once, before the send loop
    saved_path: Path | None = None
    if attachment is not None:
        try:
            saved_path = await _save_discord_attachment(bot, attachment)
        except Exception:
            logger.exception("Failed to download attachment: %s", attachment.filename)
            return error_embed("Failed to download the attached file.")

    with bot_db(bot) as conn:
        from_team = get_team_by_channel(conn, channel_id)
        if from_team is None:
            return error_embed(ERR_NO_TEAM)

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

            msg = message_service.send_message(conn, from_team.id, to_team.id, content)
            embed = inter_team_message_embed(from_team.name, content)

            # Build a discord.File from the saved attachment for each recipient.
            # discord.File consumes the stream, so we re-open the file each time.
            if (
                attachment is not None
                and saved_path is not None
                and saved_path.exists()
            ):
                file = discord.File(str(saved_path), filename=attachment.filename)
                attachment_repo.create(
                    conn,
                    filename=attachment.filename,
                    stored_path=str(saved_path),
                    content_type=infer_content_type(
                        attachment.filename, attachment.content_type
                    ),
                    size_bytes=attachment.size,
                    message_id=msg.id,
                )
                await target_channel.send(embed=embed, file=file)
            else:
                await target_channel.send(embed=embed)

            sent_to.append(to_team.name)

            att_suffix = f" (+{attachment.filename})" if attachment else ""
            logger.info(
                "Inter-team message: %s -> %s: %.80s%s",
                from_team.name,
                to_team.name,
                content,
                att_suffix,
            )

    result: discord.Embed
    if sent_to and not errors:
        result = message_sent_embed(sent_to, content)
    elif sent_to and errors:
        result = message_sent_embed(sent_to, content)
        result.add_field(
            name="Errors",
            value="\n".join(f"\u26a0\ufe0f {e}" for e in errors),
            inline=False,
        )
    else:
        return error_embed(
            "Could not send to any team:\n"
            + "\n".join(f"\u2022 {e}" for e in errors)
            + "\n\nUse `/teams` to see available teams."
        )

    if attachment is not None:
        result.add_field(
            name="Attachment",
            value=f"📎 {attachment.filename}",
            inline=False,
        )
    return result


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Messaging(bot))
