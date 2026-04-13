"""Business logic for creating and delivering injects."""

from __future__ import annotations

import sqlite3

from quiver.db.models import Inject, InjectRecipient
from quiver.repositories import event_repo, inject_repo


def send_inject(
    conn: sqlite3.Connection,
    content: str,
    team_ids: list[int],
    operator: str = "C2",
) -> Inject:
    """Create an inject targeted at the given teams.

    The inject sits in the DB until the bot's polling loop delivers it.
    Logs a game event for each targeted team.
    """
    inject = inject_repo.create(conn, content, team_ids, operator)
    # One event per team so the game log can show per-team delivery status
    for team_id in team_ids:
        event_repo.log(
            conn,
            event_type="inject_sent",
            team_id=team_id,
            details={"inject_id": inject.id, "operator": operator},
        )
    return inject


def mark_delivered(
    conn: sqlite3.Connection, recipient: InjectRecipient
) -> InjectRecipient | None:
    """Mark a recipient as delivered and log the event."""
    result = inject_repo.mark_delivered(conn, recipient.id)
    if result:
        event_repo.log(
            conn,
            event_type="inject_delivered",
            team_id=recipient.team_id,
            details={"inject_id": recipient.inject_id, "recipient_id": recipient.id},
        )
    return result
