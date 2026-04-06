"""Dashboard landing page."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, g, render_template

from quiver.repositories import (
    event_repo,
    heartbeat_repo,
    inject_repo,
    request_repo,
    team_repo,
)
from quiver.web.routes.game_log import _group_events

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index() -> str:
    teams = team_repo.get_all(g.db)
    bot_status = _get_bot_status(g.db)
    return render_template(
        "pages/dashboard.html",
        team_count=len(teams),
        bot_status=bot_status,
    )


@bp.route("/bot-status")
def bot_status_partial() -> str:
    """HTMX partial: bot online/offline indicator."""
    bot_status = _get_bot_status(g.db)
    return render_template("partials/bot_status.html", bot_status=bot_status)


@bp.route("/recent-activity")
def recent_activity_partial() -> str:
    """HTMX partial: recent activity table with full table wrapper."""
    teams_by_id = {t.id: t for t in team_repo.get_all(g.db)}
    # Fetch 30 raw rows; grouping may collapse them to ~10 display rows
    raw_events = event_repo.get_all(g.db, limit=30)
    grouped = _group_events(raw_events, teams_by_id)
    events = grouped[:10]
    return render_template("partials/recent_activity.html", events=events)


@bp.route("/stats")
def stats_partial() -> str:
    """HTMX partial: live stat cards."""
    pending_count = len(request_repo.get_pending(g.db))
    inject_count = inject_repo.count(g.db)
    request_count = request_repo.count(g.db)
    return (
        json.dumps(
            {
                "pending_count": pending_count,
                "inject_count": inject_count,
                "request_count": request_count,
            }
        ),
        200,
        {"Content-Type": "application/json"},
    )


@bp.route("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok"}, 200


def _get_bot_status(db) -> dict:
    heartbeat = heartbeat_repo.get(db)
    if heartbeat is None:
        return {
            "online": False,
            "last_beat": None,
            "guild_count": 0,
            "age_seconds": None,
        }

    now = datetime.now(timezone.utc)
    last_beat_utc = heartbeat.last_beat.replace(tzinfo=timezone.utc)
    age = (now - last_beat_utc).total_seconds()

    # Bot polls every 3 s; 15 s tolerance covers brief network hiccups
    return {
        "online": age < 15,
        "last_beat": heartbeat.last_beat,
        "guild_count": heartbeat.guild_count,
        "age_seconds": round(age),
    }
