"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    discord_token: str
    bot_command_prefix: str
    database_path: Path
    uploads_path: Path
    flask_host: str
    flask_port: int


def load_config(env_path: str | None = None) -> Config:
    """Load configuration from environment variables.

    Raises ValueError if required variables are missing.
    """
    load_dotenv(env_path)

    discord_token = os.environ.get("DISCORD_TOKEN", "")
    if not discord_token:
        raise ValueError("DISCORD_TOKEN environment variable is required")

    uploads_path = Path(os.environ.get("UPLOADS_PATH", "uploads"))
    uploads_path.mkdir(parents=True, exist_ok=True)

    return Config(
        discord_token=discord_token,
        bot_command_prefix=os.environ.get("BOT_COMMAND_PREFIX", "!"),
        database_path=Path(os.environ.get("DATABASE_PATH", "quiver.db")),
        uploads_path=uploads_path,
        flask_host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        flask_port=int(os.environ.get("FLASK_PORT", "5000")),
    )
