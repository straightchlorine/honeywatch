from ipaddress import IPv4Address, IPv6Address
from typing import Any, cast

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider

from src.config import Config
from src.extensions import init_db
from src.routes import register_blueprints


class _IPAwareJSONProvider(DefaultJSONProvider):
    """Serialize psycopg's IPv4/IPv6Address (from INET columns) as strings."""

    @staticmethod
    def default(o: Any) -> Any:  # pyright: ignore[reportIncompatibleMethodOverride]
        if isinstance(o, (IPv4Address, IPv6Address)):
            return str(o)
        return DefaultJSONProvider.default(o)


def create_app(config: object | None = None) -> Flask:
    app = Flask(__name__)
    app.json = _IPAwareJSONProvider(app)

    if config is not None:
        app.config.from_object(config)
    else:
        app.config.from_object(Config)

    db_url = cast(str, app.config["SQLALCHEMY_DATABASE_URI"])
    if db_url:
        init_db(db_url)

    register_blueprints(app)

    @app.errorhandler(404)
    def not_found(_error: Exception) -> tuple[Any, int]:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(_error: Exception) -> tuple[Any, int]:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"error": "Internal server error"}), 500

    return app
