"""Run the Quiver Discord bot."""

from quiver.bot.main import run_bot
from quiver.config import load_config
from quiver.logging_config import setup_logging


def main() -> None:
    setup_logging()
    config = load_config()
    run_bot(config)


if __name__ == "__main__":
    main()
