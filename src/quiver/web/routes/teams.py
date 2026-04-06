"""Team overview routes."""

from __future__ import annotations

from flask import Blueprint, g, render_template

from quiver.repositories import event_repo, request_repo, team_repo

bp = Blueprint("teams", __name__, url_prefix="/teams")


@bp.route("/")
def teams_page() -> str:
    teams = team_repo.get_all(g.db)
    # Fetch all requests in one query; filtered per-team below to avoid N+1
    all_requests = request_repo.get_all(g.db, limit=1000)

    team_stats = []
    for team in teams:
        team_requests = [r for r in all_requests if r.team_id == team.id]
        pending = sum(1 for r in team_requests if r.status == "pending")
        total = len(team_requests)
        recent_events = event_repo.get_all(g.db, team_id=team.id, limit=1)
        last_activity = recent_events[0].created_at if recent_events else None

        has_placeholder = team.discord_channel_id.startswith("PLACEHOLDER_")

        team_stats.append(
            {
                "team": team,
                "request_count": total,
                "pending_count": pending,
                "last_activity": last_activity,
                "channel_configured": not has_placeholder,
            }
        )

    return render_template("pages/teams.html", team_stats=team_stats)
