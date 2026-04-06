"""Business logic for inter-team messaging."""

from __future__ import annotations

import sqlite3

from quiver.db.models import InterTeamMessage
from quiver.repositories import event_repo, message_repo


def send_message(
    conn: sqlite3.Connection,
    from_team_id: int,
    to_team_id: int,
    content: str,
) -> InterTeamMessage:
    """Record an inter-team message and log events for both sides."""
    msg = message_repo.create(conn, from_team_id, to_team_id, content)
    # Two events per message: one for the sender's activity log, one for
    # the receiver's.  The game_log grouping logic collapses multi-recipient
    # sends into a single display row.
    event_repo.log(
        conn,
        event_type="inter_team_msg",
        team_id=from_team_id,
        details={
            "message_id": msg.id,
            "to_team_id": to_team_id,
            "direction": "sent",
        },
    )
    event_repo.log(
        conn,
        event_type="inter_team_msg",
        team_id=to_team_id,
        details={
            "message_id": msg.id,
            "from_team_id": from_team_id,
            "direction": "received",
        },
    )
    return msg
