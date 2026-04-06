"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("quiver.config")


@dataclass(frozen=True)
class Config:
    discord_token: str
    bot_command_prefix: str
    database_path: Path
    uploads_path: Path
    flask_host: str
    flask_port: int
    flask_secret_key: str


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

    flask_secret_key = os.environ.get("FLASK_SECRET_KEY", "")
    if not flask_secret_key:
        flask_secret_key = secrets.token_hex(32)
        logger.warning(
            "FLASK_SECRET_KEY not set — using a random key. "
            "Sessions will not persist across restarts. "
            "Set FLASK_SECRET_KEY in your .env for stable sessions."
        )

    return Config(
        discord_token=discord_token,
        bot_command_prefix=os.environ.get("BOT_COMMAND_PREFIX", "!"),
        database_path=Path(os.environ.get("DATABASE_PATH", "quiver.db")),
        uploads_path=uploads_path,
        flask_host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        flask_port=int(os.environ.get("FLASK_PORT", "5000")),
        flask_secret_key=flask_secret_key,
    )
