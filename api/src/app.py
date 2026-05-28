from ipaddress import IPv4Address, IPv6Address
from typing import Any, cast

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_smorest import Api
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


def _configure_openapi(app: Flask) -> None:
    app.config["API_TITLE"] = "Honeywatch"
    app.config["API_VERSION"] = "1.0"
    app.config["OPENAPI_VERSION"] = "3.1.0"
    app.config["OPENAPI_URL_PREFIX"] = "/api"
    app.config["OPENAPI_JSON_PATH"] = "openapi.json"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger"
    app.config["OPENAPI_SWAGGER_UI_URL"] = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    )
    app.config["OPENAPI_REDOC_PATH"] = "/redoc"
    app.config["OPENAPI_REDOC_URL"] = (
        "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
    )


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

    _configure_openapi(app)
    smorest_api = Api(app)

    db_url = cast(
        str,
        app.config.get("SQLALCHEMY_DATABASE_URI") or "",  # pyright: ignore[reportUnknownMemberType]
    )
    if db_url:
        init_db(app, db_url)

    register_blueprints(smorest_api)

    @app.errorhandler(404)
    def not_found(_error: Exception) -> tuple[Any, int]:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(_error: Exception) -> tuple[Any, int]:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"error": "Internal server error"}), 500

    return app
