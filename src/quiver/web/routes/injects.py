"""Inject composer routes."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, g, render_template, request

from quiver.repositories import attachment_repo, inject_repo, team_repo
from quiver.services import inject_service, upload_service
from quiver.validation import MAX_INJECT_CONTENT, MAX_OPERATOR_NAME
from quiver.web.app import limiter
from quiver.web.helpers import PER_PAGE, error_html, paginate
from quiver.web.helpers import teams_by_id as _teams_by_id

bp = Blueprint("injects", __name__, url_prefix="/injects")


@bp.route("/")
def inject_page() -> str:
    teams = team_repo.get_all(g.db)
    return render_template("pages/injects.html", teams=teams)


@bp.route("/", methods=["POST"])
@limiter.limit("20 per minute")
def create_inject() -> str:
    content = request.form.get("content", "").strip()
    operator = request.form.get("operator", "C2").strip() or "C2"
    team_ids = request.form.getlist("team_ids", type=int)

    if not content:
        return error_html("Inject content cannot be empty.")

    if len(content) > MAX_INJECT_CONTENT:
        return error_html(
            f"Inject content too long ({len(content)} chars, max {MAX_INJECT_CONTENT})."
        )

    if len(operator) > MAX_OPERATOR_NAME:
        return error_html(f"Operator name too long (max {MAX_OPERATOR_NAME} chars).")

    if not team_ids:
        return error_html("Select at least one team.")

    inject = inject_service.send_inject(g.db, content, team_ids, operator)

    # Handle file uploads
    files = request.files.getlist("attachments")
    uploads_path = Path(current_app.config["UPLOADS_PATH"])
    attachments = upload_service.save_uploads(
        g.db, uploads_path, files, inject_id=inject.id
    )

    team_names = []
    for tid in team_ids:
        team = team_repo.get_by_id(g.db, tid)
        if team:
            team_names.append(team.name)

    return render_template(
        "partials/inject_sent.html",
        inject=inject,
        team_names=team_names,
        attachment_count=len(attachments),
    )


@bp.route("/history")
def inject_history_partial() -> str:
    """HTMX partial: paginated inject history."""
    page = request.args.get("page", 1, type=int)
    total = inject_repo.count(g.db)
    total_pages, offset = paginate(total, page)
    recent = inject_repo.get_all(g.db, limit=PER_PAGE, offset=offset)
    tbi = _teams_by_id(g.db)

    # Enrich each inject with delivery progress and attachment counts
    injects_with_recipients = []
    for inj in recent:
        recipients = inject_repo.get_recipients(g.db, inj.id)
        team_names = [tbi[r.team_id].name for r in recipients if r.team_id in tbi]
        delivered_count = sum(1 for r in recipients if r.delivered_at is not None)
        attachments = attachment_repo.get_for_inject(g.db, inj.id)
        injects_with_recipients.append(
            {
                "inject": inj,
                "team_names": team_names,
                "delivered": delivered_count,
                "total": len(recipients),
                "attachment_count": len(attachments),
            }
        )

    return render_template(
        "partials/inject_history.html",
        injects=injects_with_recipients,
        page=page,
        total_pages=total_pages,
        total=total,
    )
