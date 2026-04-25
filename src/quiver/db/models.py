"""Immutable data objects for all database entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _parse_ts(value: str | None) -> datetime | None:
    """Parse ISO-8601 timestamps stored by SQLite's strftime."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    discord_channel_id: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict | object) -> Team:
        r = dict(row)
        return cls(
            id=r["id"],
            name=r["name"],
            discord_channel_id=r["discord_channel_id"],
            created_at=_parse_ts(r["created_at"]),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class Inject:
    id: int
    content: str
    sent_by_operator: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict | object) -> Inject:
        r = dict(row)
        return cls(
            id=r["id"],
            content=r["content"],
            sent_by_operator=r["sent_by_operator"],
            created_at=_parse_ts(r["created_at"]),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class InjectRecipient:
    id: int
    inject_id: int
    team_id: int
    delivered_at: datetime | None

    @classmethod
    def from_row(cls, row: dict | object) -> InjectRecipient:
        r = dict(row)
        return cls(
            id=r["id"],
            inject_id=r["inject_id"],
            team_id=r["team_id"],
            delivered_at=_parse_ts(r.get("delivered_at")),
        )


@dataclass(frozen=True)
class IntelRequest:
    id: int
    team_id: int
    content: str
    status: str
    response: str | None
    discord_message_id: str | None
    response_delivered_at: datetime | None
    created_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_row(cls, row: dict | object) -> IntelRequest:
        r = dict(row)
        return cls(
            id=r["id"],
            team_id=r["team_id"],
            content=r["content"],
            status=r["status"],
            response=r.get("response"),
            discord_message_id=r.get("discord_message_id"),
            response_delivered_at=_parse_ts(r.get("response_delivered_at")),
            created_at=_parse_ts(r["created_at"]),  # type: ignore[arg-type]
            resolved_at=_parse_ts(r.get("resolved_at")),
        )


@dataclass(frozen=True)
class InterTeamMessage:
    id: int
    from_team_id: int
    to_team_id: int
    content: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict | object) -> InterTeamMessage:
        r = dict(row)
        return cls(
            id=r["id"],
            from_team_id=r["from_team_id"],
            to_team_id=r["to_team_id"],
            content=r["content"],
            created_at=_parse_ts(r["created_at"]),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class GameEvent:
    id: int
    event_type: str
    team_id: int | None
    details: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict | object) -> GameEvent:
        r = dict(row)
        return cls(
            id=r["id"],
            event_type=r["event_type"],
            team_id=r.get("team_id"),
            details=r.get("details"),
            created_at=_parse_ts(r["created_at"]),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class Attachment:
    id: int
    inject_id: int | None
    request_id: int | None
    message_id: int | None
    filename: str
    stored_path: str
    content_type: str | None
    size_bytes: int | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict | object) -> Attachment:
        r = dict(row)
        return cls(
            id=r["id"],
            inject_id=r.get("inject_id"),
            request_id=r.get("request_id"),
            message_id=r.get("message_id"),
            filename=r["filename"],
            stored_path=r["stored_path"],
            content_type=r.get("content_type"),
            size_bytes=r.get("size_bytes"),
            created_at=_parse_ts(r["created_at"]),  # type: ignore[arg-type]
        )

    @property
    def is_image(self) -> bool:
        return bool(self.content_type and self.content_type.startswith("image/"))


@dataclass(frozen=True)
class GameState:
    started_at: datetime | None
    ended_at: datetime | None

    @classmethod
    def from_row(cls, row: dict | object) -> GameState:
        r = dict(row)
        return cls(
            started_at=_parse_ts(r.get("started_at")),
            ended_at=_parse_ts(r.get("ended_at")),
        )
