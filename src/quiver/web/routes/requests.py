"""Intel request queue routes."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, g, render_template, request
from markupsafe import escape

from quiver.repositories import request_repo
from quiver.services import request_service, upload_service
from quiver.validation import MAX_RESPONSE_TEXT
from quiver.web.app import limiter
from quiver.web.helpers import PER_PAGE, error_html, paginate
from quiver.web.helpers import teams_by_id as _teams_by_id

bp = Blueprint("requests", __name__, url_prefix="/requests")


@bp.route("/")
def request_page() -> str:
    teams_by_id = _teams_by_id(g.db)
    pending = request_repo.get_pending(g.db)
    return render_template(
        "pages/requests.html",
        pending=pending,
        teams_by_id=teams_by_id,
    )


@bp.route("/queue")
def queue_partial() -> str:
    """HTMX partial: full pending request queue for initial load."""
    teams_by_id = _teams_by_id(g.db)
    pending = request_repo.get_pending(g.db)
    return render_template(
        "partials/request_queue.html",
        pending=pending,
        teams_by_id=teams_by_id,
    )


@bp.route("/queue/sync")
def queue_sync() -> str:
    """Returns current pending IDs + any new card HTML via OOB swaps.

    The JS polls this endpoint. It compares server IDs against DOM IDs:
    - New cards are appended via hx-swap-oob
    - Removed cards are deleted client-side
    """
    teams_by_id = _teams_by_id(g.db)
    pending = request_repo.get_pending(g.db)
    # Incremental sync: the client sends the IDs it already has in the DOM.
    # We diff against the server's current pending set so we only render
    # HTML for truly new cards.  The client removes cards whose IDs are no
    # longer in pending_ids (i.e. resolved since last poll).
    known_ids = request.args.get("known", "")
    known_set = set()
    if known_ids:
        known_set = {int(x) for x in known_ids.split(",") if x.strip()}

    new_requests = [r for r in pending if r.id not in known_set]
    pending_ids = [r.id for r in pending]

    new_html = ""
    for req in new_requests:
        new_html += render_template(
            "partials/request_card.html",
            req=req,
            teams_by_id=teams_by_id,
        )

    return (
        json.dumps(
            {
                "pending_ids": pending_ids,
                "new_html": new_html,
                "pending_count": len(pending),
            }
        ),
        200,
        {"Content-Type": "application/json"},
    )


@bp.route("/all")
def all_partial() -> str:
    """HTMX partial: paginated all-requests table."""
    page = request.args.get("page", 1, type=int)
    total = request_repo.count(g.db)
    total_pages, offset = paginate(total, page)
    requests_list = request_repo.get_all(g.db, limit=PER_PAGE, offset=offset)
    teams_by_id = _teams_by_id(g.db)
    return render_template(
        "partials/request_all.html",
        requests=requests_list,
        teams_by_id=teams_by_id,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route("/<int:request_id>/resolve", methods=["POST"])
@limiter.limit("30 per minute")
def resolve(request_id: int) -> str:
    """Approve or deny a request, optionally with file attachments."""
    status = request.form.get("status", "").strip()
    response = request.form.get("response", "").strip() or None

    if status not in ("approved", "denied"):
        return error_html("Invalid status.")

    if response is not None and len(response) > MAX_RESPONSE_TEXT:
        return error_html(
            f"Response too long ({len(response)} chars, max {MAX_RESPONSE_TEXT})."
        )

    result = request_service.resolve_request(g.db, request_id, status, response)
    if result is None:
        return error_html("Request not found.")

    # Handle file uploads
    files = request.files.getlist("attachments")
    uploads_path = Path(current_app.config["UPLOADS_PATH"])
    attachments = upload_service.save_uploads(
        g.db, uploads_path, files, request_id=request_id
    )

    teams_by_id = _teams_by_id(g.db)
    team = teams_by_id.get(result.team_id)
    team_name = team.name if team else "Unknown"

    status_label = "APPROVED" if status == "approved" else "DENIED"
    badge_class = "approved" if status == "approved" else "denied"
    file_note = f" + {len(attachments)} file(s)" if attachments else ""
    border_colour = "#5cb85c" if status == "approved" else "#d9534f"
    return (
        f'<div class="request-resolved-notice" style="padding:0.5rem 1rem;margin-bottom:0.5rem;'
        f'border-left:4px solid {border_colour};opacity:0.8;">'
        f'<span class="status-badge {badge_class}">{status_label}</span> '
        f"Request #{request_id} from <strong>{escape(team_name)}</strong>{escape(file_note)}"
        f"</div>"
    )
