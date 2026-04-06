"""Game event log routes."""

from __future__ import annotations

import json

from flask import Blueprint, g, render_template, request

from quiver.repositories import inject_repo, message_repo, request_repo, team_repo
from quiver.services import event_service

bp = Blueprint("game_log", __name__, url_prefix="/log")

PER_PAGE = 10

EVENT_TYPE_LABELS = {
    "inject_sent": "Inject Sent",
    "inject_delivered": "Inject Delivered",
    "request_created": "Intel Request",
    "request_resolved": "Request Resolved",
    "response_delivered": "Response Delivered",
    "inter_team_msg": "Inter-Team Message",
    "bot_connected": "Bot Connected",
    "bot_reconnected": "Bot Reconnected",
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
}


def _parse_details(event) -> dict:
    try:
        return json.loads(event.details) if event.details else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _group_key(event) -> str | None:
    """Return a grouping key for events that should be collapsed, or None.

    Related events (e.g. an inject sent to 5 teams) produce 5 rows in
    game_events.  Grouping collapses them into one display row so the
    log stays readable.  Consecutive events with the same key are merged;
    events with key=None are never grouped.
    """
    data = _parse_details(event)
    etype = event.event_type

    # Injects: one event per team, but same inject_id -- collapse by inject
    if etype in ("inject_sent", "inject_delivered"):
        inject_id = data.get("inject_id")
        if inject_id is not None:
            return f"{etype}:{inject_id}"

    if etype == "inter_team_msg":
        direction = data.get("direction", "")
        message_id = data.get("message_id")
        if direction == "sent" and message_id:
            # Multi-recipient send: same sender + same second = same batch
            ts = event.created_at.strftime("%Y%m%d%H%M%S") if event.created_at else ""
            return f"msg_sent:{event.team_id}:{ts}"
        if direction == "received" and message_id:
            # Multiple teams receiving from the same sender at the same time
            from_team_id = data.get("from_team_id")
            ts = event.created_at.strftime("%Y%m%d%H%M%S") if event.created_at else ""
            return f"msg_recv:{from_team_id}:{ts}"

    return None


def _group_events(events: list, teams_by_id: dict) -> list[dict]:
    """Group related events into single display rows.

    Relies on events being sorted by created_at DESC so that related
    events (same key) appear consecutively and can be merged in one pass.
    """
    groups: list[tuple[str | None, list]] = []

    for event in events:
        key = _group_key(event)
        # Merge with the previous group only if the keys match
        if key and groups and groups[-1][0] == key:
            groups[-1][1].append(event)
        else:
            groups.append((key, [event]))

    result = []
    for key, group_events in groups:
        if len(group_events) == 1 or key is None:
            result.append(_format_single_event(group_events[0], teams_by_id))
        else:
            result.append(_format_grouped_events(key, group_events, teams_by_id))

    return result


def _format_single_event(event, teams_by_id: dict) -> dict:
    """Format a single ungrouped event."""
    team_name = (
        teams_by_id[event.team_id].name
        if event.team_id and event.team_id in teams_by_id
        else None
    )
    label = EVENT_TYPE_LABELS.get(event.event_type, event.event_type)
    icon = EVENT_TYPE_ICONS.get(event.event_type, "\u2022")
    data = _parse_details(event)

    summary = ""
    full_content = None
    etype = event.event_type

    if etype == "inject_sent":
        inject_id = data.get("inject_id")
        operator = data.get("operator", "C2")
        summary = f"Inject #{inject_id} queued by {operator}"
        if inject_id:
            inj = inject_repo.get_by_id(g.db, inject_id)
            if inj:
                full_content = inj.content

    elif etype == "inject_delivered":
        inject_id = data.get("inject_id")
        summary = f"Inject #{inject_id} delivered"
        if inject_id:
            inj = inject_repo.get_by_id(g.db, inject_id)
            if inj:
                full_content = inj.content

    elif etype == "request_created":
        request_id = data.get("request_id")
        summary = f"Request #{request_id} submitted"
        if request_id:
            req = request_repo.get_by_id(g.db, request_id)
            if req:
                full_content = req.content

    elif etype == "request_resolved":
        request_id = data.get("request_id")
        status = data.get("status", "unknown")
        summary = f"Request #{request_id} {status.upper()}"
        if request_id:
            req = request_repo.get_by_id(g.db, request_id)
            if req:
                parts = [f"Request: {req.content}"]
                if req.response:
                    parts.append(f"Response: {req.response}")
                full_content = "\n".join(parts)

    elif etype == "response_delivered":
        request_id = data.get("request_id")
        summary = f"Response for request #{request_id} delivered"
        if request_id:
            req = request_repo.get_by_id(g.db, request_id)
            if req and req.response:
                full_content = req.response

    elif etype == "inter_team_msg":
        direction = data.get("direction", "")
        message_id = data.get("message_id")
        other_team_id = data.get("to_team_id") or data.get("from_team_id")
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
            msg = message_repo.get_by_id(g.db, message_id)
            if msg:
                full_content = msg.content

    else:
        summary = event.details or ""

    return {
        "id": event.id,
        "created_at": event.created_at,
        "icon": icon,
        "label": label,
        "event_type": event.event_type,
        "team_name": team_name,
        "summary": summary,
        "full_content": full_content,
    }


def _format_grouped_events(key: str, events: list, teams_by_id: dict) -> dict:
    """Format a group of related events as a single row."""
    first = events[0]
    data = _parse_details(first)
    etype = first.event_type
    label = EVENT_TYPE_LABELS.get(etype, etype)
    icon = EVENT_TYPE_ICONS.get(etype, "\u2022")

    team_names = []
    for e in events:
        tid = e.team_id
        if tid and tid in teams_by_id:
            name = teams_by_id[tid].name
            if name not in team_names:
                team_names.append(name)

    teams_str = ", ".join(team_names)
    summary = ""
    full_content = None

    if etype == "inject_sent":
        inject_id = data.get("inject_id")
        operator = data.get("operator", "C2")
        summary = f"Inject #{inject_id} queued by {operator} to {teams_str}"
        if inject_id:
            inj = inject_repo.get_by_id(g.db, inject_id)
            if inj:
                full_content = inj.content

    elif etype == "inject_delivered":
        inject_id = data.get("inject_id")
        summary = f"Inject #{inject_id} delivered to {teams_str}"
        if inject_id:
            inj = inject_repo.get_by_id(g.db, inject_id)
            if inj:
                full_content = inj.content

    elif etype == "inter_team_msg":
        direction = data.get("direction", "")
        # For sent: all events share same sender (team_id on first event)
        # Collect the "other" team names
        other_names = []
        message_id = None
        for e in events:
            d = _parse_details(e)
            other_id = d.get("to_team_id") or d.get("from_team_id")
            if other_id and other_id in teams_by_id:
                name = teams_by_id[other_id].name
                if name not in other_names:
                    other_names.append(name)
            if not message_id:
                message_id = d.get("message_id")

        others_str = ", ".join(other_names)
        sender_name = (
            teams_by_id[first.team_id].name
            if first.team_id and first.team_id in teams_by_id
            else "Unknown"
        )

        if direction == "sent":
            summary = f"Sent to {others_str}"
            # Team column shows the sender
        elif direction == "received":
            from_id = _parse_details(first).get("from_team_id")
            from_name = (
                teams_by_id[from_id].name
                if from_id and from_id in teams_by_id
                else "Unknown"
            )
            summary = f"Received by {teams_str} from {from_name}"
            sender_name = None  # No single team for the team column

        if message_id:
            msg = message_repo.get_by_id(g.db, message_id)
            if msg:
                full_content = msg.content

        return {
            "id": first.id,
            "created_at": first.created_at,
            "icon": icon,
            "label": label,
            "event_type": etype,
            "team_name": sender_name if direction == "sent" else teams_str,
            "summary": summary,
            "full_content": full_content,
        }

    return {
        "id": first.id,
        "created_at": first.created_at,
        "icon": icon,
        "label": label,
        "event_type": etype,
        "team_name": teams_str,
        "summary": summary,
        "full_content": full_content,
    }


def _count_groups(events: list) -> int:
    """Count how many groups a list of events produces (no formatting, fast)."""
    count = 0
    prev_key = object()  # sentinel
    for event in events:
        key = _group_key(event)
        if key is None or key != prev_key:
            count += 1
        prev_key = key
    return count


def _slice_groups(events: list, group_start: int, group_count: int) -> list:
    """Extract the raw events belonging to groups[group_start:group_start+group_count].

    Single-pass scan that avoids formatting events outside the visible page.
    """
    current_group = -1
    prev_key = object()
    result = []
    collecting = False

    for event in events:
        key = _group_key(event)
        if key is None or key != prev_key:
            current_group += 1
        prev_key = key

        if current_group >= group_start and current_group < group_start + group_count:
            collecting = True
            result.append(event)
        elif collecting:
            break  # Past the window

    return result


# Keep this for the dashboard import
def _format_event(event, teams_by_id: dict) -> dict:
    return _format_single_event(event, teams_by_id)


@bp.route("/")
def log_page() -> str:
    teams = team_repo.get_all(g.db)
    return render_template(
        "pages/game_log.html",
        teams=teams,
        event_type_labels=EVENT_TYPE_LABELS,
    )


@bp.route("/data")
def log_data() -> str:
    """HTMX partial: paginated, filterable event log with grouped events."""
    event_type = request.args.get("event_type", "")
    team_id = request.args.get("team_id", "")
    page = request.args.get("page", 1, type=int)

    filter_event_type = event_type if event_type else None
    filter_team_id = int(team_id) if team_id else None

    # Grouping changes the row count (N raw events -> fewer display rows),
    # so we can't paginate with a simple SQL OFFSET.  Instead we fetch all
    # raw events, count groups cheaply via _count_groups, then slice only
    # the groups we need for the current page before doing expensive
    # formatting.
    raw_total = event_service.count_events(g.db, filter_event_type, filter_team_id)
    all_raw = event_service.get_events(
        g.db,
        filter_event_type,
        filter_team_id,
        limit=raw_total,
        offset=0,
    )

    teams_by_id = {t.id: t for t in team_repo.get_all(g.db)}

    # Fast pass: count groups without formatting (no DB lookups)
    group_count = _count_groups(all_raw)
    total = group_count
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    # Only format the page we need — find the raw offset for this page
    start = (page - 1) * PER_PAGE
    page_raw = _slice_groups(all_raw, start, PER_PAGE)
    page_events = _group_events(page_raw, teams_by_id)

    return render_template(
        "partials/game_log_table.html",
        events=page_events,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route("/partial")
def log_partial() -> str:
    """HTMX partial: recent events for dashboard (ungrouped, simple)."""
    limit = request.args.get("limit", 10, type=int)
    events = event_service.get_events(g.db, limit=limit)
    teams_by_id = {t.id: t for t in team_repo.get_all(g.db)}
    formatted = [_format_single_event(e, teams_by_id) for e in events]
    return render_template(
        "partials/event_table.html",
        events=formatted,
    )
