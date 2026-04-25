import os
from ipaddress import IPv4Address, IPv6Address
from typing import Any, cast

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider

from src.config import Config, require_secret_key
from src.extensions import init_db
from src.routes import register_blueprints


class _IPAwareJSONProvider(DefaultJSONProvider):
    """JSON provider that serialises psycopg ``IPv4Address`` / ``IPv6Address``
    values (returned from Postgres INET columns) as strings."""

    @staticmethod
    def default(o: Any) -> Any:  # pyright: ignore[reportIncompatibleMethodOverride]
        if isinstance(o, (IPv4Address, IPv6Address)):
            return str(o)
        return DefaultJSONProvider.default(o)


def create_app(config: object | None = None) -> Flask:
    """Build and configure the Flask application.

    Args:
        config: Optional config object. Defaults to :class:`Config`; tests
            pass :class:`TestConfig`.

    Returns:
        A fully wired Flask app: IP-aware JSON provider, DB engine and
        session factory attached to ``app.extensions``, blueprints
        registered, JSON error handlers installed.
    """
    app = Flask(__name__)
    app.json = _IPAwareJSONProvider(app)

    if config is not None:
        app.config.from_object(config)
    else:
        app.config.from_object(Config)

    if app.config.get("TESTING"):  # pyright: ignore[reportUnknownMemberType]
        os.environ.setdefault("TESTING", "1")
    secret_key = require_secret_key()
    app.config["FLASK_SECRET_KEY"] = secret_key
    app.config["SECRET_KEY"] = secret_key

    db_url = cast(str, app.config.get("SQLALCHEMY_DATABASE_URI") or "")  # pyright: ignore[reportUnknownMemberType]
    if db_url:
        init_db(app, db_url)

    register_blueprints(app)

    @app.errorhandler(404)
    def not_found(_error: Exception) -> tuple[Any, int]:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(_error: Exception) -> tuple[Any, int]:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"error": "Internal server error"}), 500

    return app
