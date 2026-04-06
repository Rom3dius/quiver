"""Business logic for intel requests."""

from __future__ import annotations

import sqlite3

from quiver.db.models import IntelRequest
from quiver.repositories import event_repo, request_repo


def create_request(
    conn: sqlite3.Connection,
    team_id: int,
    content: str,
    discord_message_id: str | None = None,
) -> IntelRequest:
    """Record a new intel request from a team."""
    request = request_repo.create(conn, team_id, content, discord_message_id)
    event_repo.log(
        conn,
        event_type="request_created",
        team_id=team_id,
        details={"request_id": request.id},
    )
    return request


def resolve_request(
    conn: sqlite3.Connection,
    request_id: int,
    status: str,
    response: str | None = None,
) -> IntelRequest | None:
    """Approve or deny an intel request with an optional response message."""
    result = request_repo.resolve(conn, request_id, status, response)
    if result:
        event_repo.log(
            conn,
            event_type="request_resolved",
            team_id=result.team_id,
            details={
                "request_id": result.id,
                "status": status,
            },
        )
    return result


def mark_response_delivered(
    conn: sqlite3.Connection, request_id: int
) -> IntelRequest | None:
    """Mark that the bot has delivered the response to Discord."""
    result = request_repo.mark_response_delivered(conn, request_id)
    if result:
        event_repo.log(
            conn,
            event_type="response_delivered",
            team_id=result.team_id,
            details={"request_id": result.id},
        )
    return result
