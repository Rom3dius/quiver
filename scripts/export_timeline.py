"""Export a self-contained HTML timeline and a raw database copy.

Usage:
    python scripts/export_timeline.py
    python scripts/export_timeline.py --db quiver.db --out exports/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# ---------------------------------------------------------------------------
# Resolve project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src" / "quiver"
TEMPLATE_DIR = SRC_ROOT / "web" / "templates"
STYLE_PATH = SRC_ROOT / "web" / "static" / "style.css"

# Add src/ to path so we can import quiver modules
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quiver.db.connection import get_connection  # noqa: E402
from quiver.repositories import (  # noqa: E402
    event_repo,
    game_state_repo,
    inject_repo,
    message_repo,
    request_repo,
    team_repo,
)

# ---------------------------------------------------------------------------
# Event display constants (shared with game_log.py)
# ---------------------------------------------------------------------------
EVENT_TYPE_LABELS = {
    "inject_sent": "Inject Sent",
    "inject_delivered": "Inject Delivered",
    "request_created": "Intel Request",
    "request_resolved": "Request Resolved",
    "response_delivered": "Response Delivered",
    "inter_team_msg": "Inter-Team Message",
    "bot_connected": "Bot Connected",
    "bot_reconnected": "Bot Reconnected",
    "game_started": "Game Started",
    "game_ended": "Game Ended",
}

EVENT_TYPE_ICONS = {
    "inject_sent": "\U0001f4e1",
    "inject_delivered": "\u2705",
    "request_created": "\U0001f4e9",
    "request_resolved": "\U0001f4cb",
    "response_delivered": "\U0001f4e8",
    "inter_team_msg": "\U0001f4ac",
    "bot_connected": "\U0001f7e2",
    "bot_reconnected": "\U0001f504",
    "game_started": "\U0001f3ae",
    "game_ended": "\U0001f3c1",
}

# Event types participants care about (filter out bot system noise)
PARTICIPANT_EVENT_TYPES = {
    "inject_sent",
    "inject_delivered",
    "request_created",
    "request_resolved",
    "response_delivered",
    "inter_team_msg",
    "game_started",
    "game_ended",
}

# Categories for the filter UI (lists, not sets, for JSON serialization)
EVENT_CATEGORIES = {
    "injects": ["inject_sent", "inject_delivered"],
    "requests": ["request_created", "request_resolved", "response_delivered"],
    "messages": ["inter_team_msg"],
    "system": ["game_started", "game_ended", "bot_connected", "bot_reconnected"],
}


# ---------------------------------------------------------------------------
# Timeline entry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TimelineEntry:
    """A single formatted event for the timeline."""

    timestamp: datetime
    icon: str
    label: str
    event_type: str
    team_name: str | None
    team_id: int | None
    summary: str
    content: str | None
    group_key: str | None


# ---------------------------------------------------------------------------
# Data loading and formatting
# ---------------------------------------------------------------------------


def _parse_details(details_str: str | None) -> dict:
    if not details_str:
        return {}
    try:
        return json.loads(details_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _group_key(event) -> str | None:
    """Return a grouping key for related events, or None."""
    data = _parse_details(event.details)
    etype = event.event_type

    if etype in ("inject_sent", "inject_delivered"):
        inject_id = data.get("inject_id")
        if inject_id is not None:
            return f"{etype}:{inject_id}"

    if etype == "inter_team_msg":
        direction = data.get("direction", "")
        message_id = data.get("message_id")
        if direction == "sent" and message_id:
            ts = event.created_at.strftime("%Y%m%d%H%M%S") if event.created_at else ""
            return f"msg_sent:{event.team_id}:{ts}"
        if direction == "received" and message_id:
            from_team_id = data.get("from_team_id")
            ts = event.created_at.strftime("%Y%m%d%H%M%S") if event.created_at else ""
            return f"msg_recv:{from_team_id}:{ts}"

    return None


def _load_all_data(conn: sqlite3.Connection) -> dict:
    """Load all data needed for the timeline."""
    # Count total events to set limit
    total_events = event_repo.count(conn)

    teams = team_repo.get_all(conn)
    teams_by_id = {t.id: t for t in teams}

    game_state = game_state_repo.get(conn)

    all_events = event_repo.get_all(conn, limit=max(total_events, 1), offset=0)
    # Reverse to chronological ASC (repo returns DESC)
    all_events = list(reversed(all_events))

    # Pre-load all injects, requests, messages for content lookup
    inject_count = inject_repo.count(conn)
    all_injects = inject_repo.get_all(conn, limit=max(inject_count, 1))
    injects_by_id = {i.id: i for i in all_injects}

    request_count = request_repo.count(conn)
    all_requests = request_repo.get_all(conn, limit=max(request_count, 1))
    requests_by_id = {r.id: r for r in all_requests}

    msg_count = message_repo.count(conn)
    all_messages = message_repo.get_all(conn, limit=max(msg_count, 1))
    messages_by_id = {m.id: m for m in all_messages}

    request_summary = request_repo.request_summary(conn)

    return {
        "teams": teams,
        "teams_by_id": teams_by_id,
        "game_state": game_state,
        "all_events": all_events,
        "injects_by_id": injects_by_id,
        "requests_by_id": requests_by_id,
        "messages_by_id": messages_by_id,
        "request_summary": request_summary,
        "total_injects": inject_count,
        "total_messages": msg_count,
    }


def _format_event(
    event,
    data: dict,
    teams_by_id: dict,
    injects_by_id: dict,
    requests_by_id: dict,
    messages_by_id: dict,
) -> TimelineEntry:
    """Format a single event into a TimelineEntry."""
    etype = event.event_type
    details = _parse_details(event.details)
    team_name = (
        teams_by_id[event.team_id].name
        if event.team_id and event.team_id in teams_by_id
        else None
    )
    icon = EVENT_TYPE_ICONS.get(etype, "\u2022")
    label = EVENT_TYPE_LABELS.get(etype, etype)

    summary = ""
    content = None

    if etype == "inject_sent":
        inject_id = details.get("inject_id")
        operator = details.get("operator", "C2")
        summary = f"Inject #{inject_id} queued by {operator}"
        inj = injects_by_id.get(inject_id)
        if inj:
            content = inj.content

    elif etype == "inject_delivered":
        inject_id = details.get("inject_id")
        summary = f"Inject #{inject_id} delivered"
        inj = injects_by_id.get(inject_id)
        if inj:
            content = inj.content

    elif etype == "request_created":
        request_id = details.get("request_id")
        summary = f"Request #{request_id} submitted"
        req = requests_by_id.get(request_id)
        if req:
            content = req.content

    elif etype == "request_resolved":
        request_id = details.get("request_id")
        status = details.get("status", "unknown")
        summary = f"Request #{request_id} {status.upper()}"
        req = requests_by_id.get(request_id)
        if req:
            parts = [f"Request: {req.content}"]
            if req.response:
                parts.append(f"Response: {req.response}")
            content = "\n".join(parts)

    elif etype == "response_delivered":
        request_id = details.get("request_id")
        summary = f"Response for request #{request_id} delivered"
        req = requests_by_id.get(request_id)
        if req and req.response:
            content = req.response

    elif etype == "inter_team_msg":
        direction = details.get("direction", "")
        message_id = details.get("message_id")
        other_team_id = details.get("to_team_id") or details.get("from_team_id")
        other_name = (
            teams_by_id[other_team_id].name
            if other_team_id and other_team_id in teams_by_id
            else "Unknown"
        )
        if direction == "sent":
            summary = f"Sent to {other_name}"
        elif direction == "received":
            summary = f"Received from {other_name}"
        if message_id:
            msg = messages_by_id.get(message_id)
            if msg:
                content = msg.content

    elif etype == "game_started":
        summary = "Game clock started"

    elif etype == "game_ended":
        summary = "Game clock stopped"

    else:
        summary = event.details or ""

    return TimelineEntry(
        timestamp=event.created_at,
        icon=icon,
        label=label,
        event_type=etype,
        team_name=team_name,
        team_id=event.team_id,
        summary=summary,
        content=content,
        group_key=_group_key(event),
    )


def _group_entries(entries: list[TimelineEntry]) -> list[TimelineEntry]:
    """Merge consecutive entries with the same group_key into single entries."""
    if not entries:
        return []

    result: list[TimelineEntry] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        if entry.group_key is None:
            result.append(entry)
            i += 1
            continue

        # Collect all consecutive entries with the same key
        group = [entry]
        j = i + 1
        while j < len(entries) and entries[j].group_key == entry.group_key:
            group.append(entries[j])
            j += 1

        if len(group) == 1:
            result.append(entry)
        else:
            # Merge: collect team names
            team_names = []
            for e in group:
                if e.team_name and e.team_name not in team_names:
                    team_names.append(e.team_name)
            teams_str = ", ".join(team_names)

            # Build merged summary
            etype = entry.event_type
            if etype == "inject_sent":
                merged_summary = f"{entry.summary} to {teams_str}"
            elif etype == "inject_delivered":
                merged_summary = f"{entry.summary} to {teams_str}"
            elif etype == "inter_team_msg":
                merged_summary = f"{entry.summary} ({teams_str})"
            else:
                merged_summary = f"{entry.summary} ({teams_str})"

            merged = TimelineEntry(
                timestamp=entry.timestamp,
                icon=entry.icon,
                label=entry.label,
                event_type=entry.event_type,
                team_name=teams_str,
                team_id=entry.team_id,
                summary=merged_summary,
                content=entry.content,
                group_key=entry.group_key,
            )
            result.append(merged)

        i = j

    return result


def _parse_details_from_summary(entry: TimelineEntry) -> dict:
    """Placeholder — group merging uses the summary text directly."""
    return {}


# ---------------------------------------------------------------------------
# Time block grouping
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeBlock:
    """A 15-minute block of timeline entries."""

    start: datetime
    end: datetime
    entries: tuple[TimelineEntry, ...]
    inject_count: int
    request_count: int
    message_count: int
    system_count: int


def _build_time_blocks(
    entries: list[TimelineEntry], block_minutes: int = 15
) -> list[TimeBlock]:
    """Group entries into fixed-duration time blocks."""
    if not entries:
        return []

    delta = timedelta(minutes=block_minutes)

    # Find the range and align to block boundaries
    first_ts = entries[0].timestamp
    block_start = first_ts.replace(
        minute=(first_ts.minute // block_minutes) * block_minutes,
        second=0,
        microsecond=0,
    )

    blocks: list[TimeBlock] = []
    block_entries: list[TimelineEntry] = []
    block_end = block_start + delta

    for entry in entries:
        # Advance block window until the entry fits
        while entry.timestamp >= block_end:
            if block_entries:
                blocks.append(_make_block(block_start, block_end, block_entries))
                block_entries = []
            block_start = block_end
            block_end = block_start + delta

        block_entries.append(entry)

    # Final block
    if block_entries:
        blocks.append(_make_block(block_start, block_end, block_entries))

    return blocks


def _make_block(
    start: datetime, end: datetime, entries: list[TimelineEntry]
) -> TimeBlock:
    inject_count = sum(
        1 for e in entries if e.event_type in EVENT_CATEGORIES["injects"]
    )
    request_count = sum(
        1 for e in entries if e.event_type in EVENT_CATEGORIES["requests"]
    )
    message_count = sum(
        1 for e in entries if e.event_type in EVENT_CATEGORIES["messages"]
    )
    system_count = sum(1 for e in entries if e.event_type in EVENT_CATEGORIES["system"])
    return TimeBlock(
        start=start,
        end=end,
        entries=tuple(entries),
        inject_count=inject_count,
        request_count=request_count,
        message_count=message_count,
        system_count=system_count,
    )


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _render_html(
    blocks: list[TimeBlock],
    teams: list,
    game_state,
    stats: dict,
    css_content: str,
) -> str:
    """Render the timeline HTML using Jinja2."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("export/timeline.html")

    # Compute game duration
    duration_str = ""
    if game_state and game_state.started_at:
        end = game_state.ended_at or datetime.now(UTC)
        delta = end - game_state.started_at
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m"

    return template.render(
        blocks=blocks,
        teams=teams,
        game_state=game_state,
        duration_str=duration_str,
        stats=stats,
        css_content=css_content,
        event_categories=EVENT_CATEGORIES,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Export wargame timeline")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("quiver.db"),
        help="Path to the SQLite database (default: quiver.db)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("exports"),
        help="Output base directory (default: exports/)",
    )
    args = parser.parse_args()

    db_path: Path = args.db
    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir: Path = args.out / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    conn = get_connection(db_path)
    try:
        data = _load_all_data(conn)
    finally:
        conn.close()

    # Format all events into timeline entries
    raw_entries = [
        _format_event(
            event,
            data,
            data["teams_by_id"],
            data["injects_by_id"],
            data["requests_by_id"],
            data["messages_by_id"],
        )
        for event in data["all_events"]
        if event.event_type in PARTICIPANT_EVENT_TYPES
    ]

    # Group related events (e.g. inject sent to 4 teams -> 1 row)
    grouped_entries = _group_entries(raw_entries)

    # Build 15-minute time blocks
    blocks = _build_time_blocks(grouped_entries)

    # Summary stats
    stats = {
        "total_events": len(raw_entries),
        "total_injects": data["total_injects"],
        "total_messages": data["total_messages"],
        "requests_approved": data["request_summary"]["approved"],
        "requests_denied": data["request_summary"]["denied"],
        "requests_total": data["request_summary"]["total"],
    }

    # Read CSS for inlining
    css_content = STYLE_PATH.read_text() if STYLE_PATH.exists() else ""

    # Render HTML
    html = _render_html(
        blocks=blocks,
        teams=data["teams"],
        game_state=data["game_state"],
        stats=stats,
        css_content=css_content,
    )

    # Write outputs
    html_path = out_dir / "timeline.html"
    html_path.write_text(html, encoding="utf-8")

    db_dest = out_dir / "quiver.db"
    shutil.copy2(db_path, db_dest)

    print(f"Timeline exported to {out_dir}/")
    print(f"  {html_path.name}  ({html_path.stat().st_size / 1024:.0f} KB)")
    print(f"  {db_dest.name}     ({db_dest.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
