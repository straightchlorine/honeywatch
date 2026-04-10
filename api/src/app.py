from typing import Any, cast

from flask import Flask, jsonify

from src.config import Config
from src.extensions import init_db
from src.routes import register_blueprints


def create_app(config: object | None = None) -> Flask:
    app = Flask(__name__)

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
