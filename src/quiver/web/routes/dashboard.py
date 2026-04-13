"""Dashboard — live operations display with game controls."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, render_template

from quiver.repositories import (
    event_repo,
    game_state_repo,
    heartbeat_repo,
    inject_repo,
    message_repo,
    request_repo,
    team_repo,
)

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index() -> str:
    return render_template("pages/dashboard.html")


# --- Game controls ---


@bp.route("/game/start", methods=["POST"])
def game_start():
    """Start the game clock."""
    state = game_state_repo.start(g.db)
    event_repo.log(g.db, "game_started")
    return jsonify(
        started_at=state.started_at.isoformat() if state.started_at else None,
        ended_at=None,
    )


@bp.route("/game/stop", methods=["POST"])
def game_stop():
    """Stop the game clock."""
    state = game_state_repo.stop(g.db)
    event_repo.log(g.db, "game_ended")
    return jsonify(
        started_at=state.started_at.isoformat() if state.started_at else None,
        ended_at=state.ended_at.isoformat() if state.ended_at else None,
    )


@bp.route("/game/state")
def game_state():
    """Return current game state as JSON for the clock JS."""
    state = game_state_repo.get(g.db)
    if state is None:
        return jsonify(started_at=None, ended_at=None)
    return jsonify(
        started_at=state.started_at.isoformat() if state.started_at else None,
        ended_at=state.ended_at.isoformat() if state.ended_at else None,
    )


# --- Live data endpoints ---


@bp.route("/pulse")
def pulse_data():
    """JSON endpoint returning live dashboard metrics."""
    game = game_state_repo.get(g.db)
    game_data = {"started_at": None, "ended_at": None}
    if game is not None:
        game_data = {
            "started_at": game.started_at.isoformat() if game.started_at else None,
            "ended_at": game.ended_at.isoformat() if game.ended_at else None,
        }

    bot_status = _get_bot_status(g.db)
    teams = team_repo.get_all(g.db)
    pending_count = len(request_repo.get_pending(g.db))
    inject_count = inject_repo.count(g.db)
    request_count = request_repo.count(g.db)
    message_count = message_repo.count(g.db)

    summary = request_repo.request_summary(g.db)
    resolved = summary["approved"] + summary["denied"]
    approval_rate = round(summary["approved"] / resolved * 100) if resolved > 0 else 0

    rows = g.db.execute(
        """SELECT t.name, COUNT(e.id) as event_count
           FROM teams t
           LEFT JOIN game_events e ON e.team_id = t.id
               AND e.created_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '-15 minutes')
           GROUP BY t.id ORDER BY event_count DESC"""
    ).fetchall()
    team_activity = [{"name": r["name"], "events": r["event_count"]} for r in rows]

    rate_buckets = event_repo.get_rate_buckets(g.db)

    payload = {
        "game": game_data,
        "bot": {
            "online": bot_status["online"],
            "age_seconds": bot_status["age_seconds"],
        },
        "counters": {
            "teams": len(teams),
            "pending_requests": pending_count,
            "total_injects": inject_count,
            "total_requests": request_count,
            "total_messages": message_count,
            "approval_rate": approval_rate,
        },
        "team_activity": team_activity,
        "rate_buckets": rate_buckets,
    }
    return json.dumps(payload), 200, {"Content-Type": "application/json"}


@bp.route("/timeline")
def timeline_data():
    """JSON endpoint returning events from the last 30 minutes."""
    teams = team_repo.get_all(g.db)
    team_map = {t.id: t.name for t in teams}

    rows = g.db.execute(
        """SELECT id, event_type, team_id, details, created_at
           FROM game_events
           WHERE created_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '-30 minutes')
             AND event_type NOT IN ('inject_delivered', 'response_delivered')
           ORDER BY created_at""",
    ).fetchall()

    events = []
    for r in rows:
        team_name = team_map.get(r["team_id"]) if r["team_id"] else None
        etype = r["event_type"]

        if etype == "request_resolved" and r["details"]:
            try:
                details = json.loads(r["details"])
                status = details.get("status", "")
                if status in ("approved", "denied"):
                    etype = f"request_resolved_{status}"
            except (json.JSONDecodeError, TypeError):
                pass

        events.append(
            {
                "t": r["created_at"],
                "type": etype,
                "team": team_name,
            }
        )

    team_names = [t.name for t in teams]
    return (
        json.dumps({"events": events, "teams": team_names}),
        200,
        {"Content-Type": "application/json"},
    )


@bp.route("/comms")
def comms_data():
    """JSON endpoint for vis.js communication network graph."""
    teams = team_repo.get_all(g.db)
    matrix = message_repo.get_comm_matrix(g.db)

    team_events = {}
    for t in teams:
        team_events[t.id] = event_repo.count(g.db, team_id=t.id)

    nodes = [
        {
            "id": t.id,
            "label": t.name,
            "value": max(1, team_events.get(t.id, 0)),
        }
        for t in teams
    ]
    edges = [
        {
            "from": from_id,
            "to": to_id,
            "value": cnt,
            "title": f"{cnt} messages",
        }
        for from_id, to_id, cnt in matrix
    ]
    return (
        json.dumps({"nodes": nodes, "edges": edges}),
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

    return {
        "online": age < 15,
        "last_beat": heartbeat.last_beat,
        "guild_count": heartbeat.guild_count,
        "age_seconds": round(age),
    }
