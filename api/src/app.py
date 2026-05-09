from ipaddress import IPv4Address, IPv6Address
from typing import Any, cast

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix

from src.config import require_secret_key, select_config
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
        config: Optional config class/object. When ``None``, the class is
            resolved from ``ENVIRONMENT`` via :func:`select_config`
            (``development``/``production``). Tests inject
            :class:`TestingConfig` directly.

    Returns:
        A fully wired Flask app: IP-aware JSON provider, DB engine and
        session factory attached to ``app.extensions``, blueprints
        registered, JSON error handlers installed.
    """
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)  # pyright: ignore[reportAttributeAccessIssue]
    app.json = _IPAwareJSONProvider(app)

    if config is None:
        config = select_config()
    app.config.from_object(config)

    app.config["MAX_CONTENT_LENGTH"] = 8192

    secret_key = require_secret_key()
    app.config["FLASK_SECRET_KEY"] = secret_key
    app.config["SECRET_KEY"] = secret_key

    db_url = cast(str, app.config.get("SQLALCHEMY_DATABASE_URI") or "")
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
