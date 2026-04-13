"""Shared helpers for web route modules."""

from __future__ import annotations

import sqlite3

from markupsafe import escape

from quiver.repositories import team_repo

# Pagination page size used across all paginated routes
PER_PAGE = 10


def teams_by_id(db: sqlite3.Connection) -> dict:
    """Build a {team_id: Team} lookup dict."""
    return {t.id: t for t in team_repo.get_all(db)}


def paginate(total: int, page: int) -> tuple[int, int]:
    """Return (total_pages, offset) for the given page."""
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    offset = (page - 1) * PER_PAGE
    return total_pages, offset


def error_html(message: str) -> str:
    """Return an inline error div for HTMX responses."""
    return (
        '<div class="flash-success" style="border-color:#d9534f;background:#4a2d2d;">'
        f"{escape(message)}</div>"
    )
