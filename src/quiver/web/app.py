"""Flask application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, g, render_template
from flask import request as flask_request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from quiver.config import Config
from quiver.db.connection import get_connection
from quiver.db.migrate import init_db
from quiver.validation import MAX_REQUEST_SIZE_BYTES

logger = logging.getLogger("quiver.web")

csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"],
    storage_uri="memory://",
)


def create_app(config: Config | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    if config is None:
        from quiver.config import load_config

        config = load_config()

    app.config["DATABASE_PATH"] = str(config.database_path)
    app.config["UPLOADS_PATH"] = str(config.uploads_path)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_SIZE_BYTES
    app.config["SECRET_KEY"] = config.flask_secret_key

    csrf.init_app(app)
    limiter.init_app(app)

    # Initialize DB on startup
    with app.app_context():
        conn = get_connection(config.database_path)
        try:
            init_db(conn)
        finally:
            conn.close()

    # Per-request connection lifecycle: open before each request, close after.
    # Each request gets its own connection so WAL mode can handle concurrency.
    @app.before_request
    def open_db() -> None:
        g.db = get_connection(app.config["DATABASE_PATH"])

    @app.teardown_appcontext
    def close_db(exc: BaseException | None = None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.after_request
    def set_security_headers(response):
        # Content Security Policy — allow CDN resources used by base.html
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.after_request
    def log_request(response):
        if flask_request.path != "/health":
            logger.info(
                "%s %s %s",
                flask_request.method,
                flask_request.path,
                response.status_code,
            )
        return response

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/500.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Internal server error: %s", e)
        return render_template("errors/500.html"), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        logger.exception("Unhandled exception: %s", e)
        return render_template("errors/500.html"), 500

    # Register blueprints
    from quiver.web.routes.dashboard import bp as dashboard_bp
    from quiver.web.routes.game_log import bp as game_log_bp
    from quiver.web.routes.injects import bp as injects_bp
    from quiver.web.routes.requests import bp as requests_bp
    from quiver.web.routes.teams import bp as teams_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(injects_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(game_log_bp)
    app.register_blueprint(teams_bp)

    return app
