"""Run the Quiver C2 web dashboard."""

import os

from quiver.config import load_config
from quiver.logging_config import setup_logging
from quiver.web.app import create_app


def main() -> None:
    setup_logging()
    config = load_config()
    app = create_app(config)
    debug = os.environ.get("FLASK_DEBUG", "1") != "0"
    app.run(host=config.flask_host, port=config.flask_port, debug=debug)


if __name__ == "__main__":
    main()
