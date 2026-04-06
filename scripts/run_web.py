"""Run the Quiver C2 web dashboard."""

from quiver.config import load_config
from quiver.logging_config import setup_logging
from quiver.web.app import create_app


def main() -> None:
    setup_logging()
    config = load_config()
    app = create_app(config)
    app.run(host=config.flask_host, port=config.flask_port, debug=True)


if __name__ == "__main__":
    main()
