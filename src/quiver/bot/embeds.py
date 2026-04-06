"""Discord embed builders for all bot message types."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

# Embed sidebar colours — chosen for quick visual scanning in Discord
COLOUR_INJECT = 0x3498DB  # Blue
COLOUR_APPROVED = 0x2ECC71  # Green
COLOUR_DENIED = 0xE74C3C  # Red
COLOUR_MESSAGE = 0xF39C12  # Amber
COLOUR_INFO = 0x9B59B6  # Purple
COLOUR_SYSTEM = 0x95A5A6  # Grey


def inject_embed(content: str, operator: str = "C2") -> discord.Embed:
    embed = discord.Embed(
        title="\U0001f4e1 INTEL INJECT",
        description=content,
        colour=COLOUR_INJECT,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"Sent by {operator}")
    return embed


def request_received_embed(request_id: int, content: str) -> discord.Embed:
    embed = discord.Embed(
        title="\U0001f4e9 Intel Request Submitted",
        description=content,
        colour=COLOUR_INFO,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"Request #{request_id} — awaiting C2 response")
    return embed


def request_response_embed(
    status: str,
    original_request: str,
    response_text: str | None,
) -> discord.Embed:
    approved = status == "approved"
    embed = discord.Embed(
        title=f"{'✅' if approved else '❌'} Intel Request {'APPROVED' if approved else 'DENIED'}",
        colour=COLOUR_APPROVED if approved else COLOUR_DENIED,
        timestamp=datetime.now(timezone.utc),
    )
    # Truncate original request for the field
    short_request = original_request[:200]
    if len(original_request) > 200:
        short_request += "..."
    embed.add_field(name="Your Request", value=short_request, inline=False)
    embed.add_field(
        name="C2 Response",
        value=response_text or "No additional details.",
        inline=False,
    )
    embed.set_footer(text="Command & Control")
    return embed


def inter_team_message_embed(from_team_name: str, content: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"\U0001f4ac Message from {from_team_name}",
        description=content,
        colour=COLOUR_MESSAGE,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="Inter-team communication")
    return embed


def status_embed(team_name: str, channel_id: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"Team: {team_name}",
        colour=COLOUR_INFO,
    )
    embed.add_field(name="Channel", value=f"<#{channel_id}>", inline=True)
    embed.add_field(
        name="Commands",
        value=(
            "`!request <text>` or `/request` — Submit intel request\n"
            "`!msg <Team1,Team2> <text>` or `/msg` — Message one or more teams\n"
            "`!teams` or `/teams` — List all teams\n"
            "`!status` or `/status` — Show this info\n"
            "`!help` — Full command list"
        ),
        inline=False,
    )
    return embed


def teams_list_embed(team_names: list[str]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Teams ({len(team_names)})",
        description=", ".join(team_names),
        colour=COLOUR_INFO,
    )
    return embed


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        description=f"⚠️ {message}",
        colour=COLOUR_DENIED,
    )


def message_sent_embed(to_team_names: list[str], content: str) -> discord.Embed:
    names = ", ".join(f"**{n}**" for n in to_team_names)
    embed = discord.Embed(
        description=f"\U0001f4e8 Message sent to {names}",
        colour=COLOUR_MESSAGE,
    )
    embed.add_field(name="Message", value=content[:1024], inline=False)
    return embed
