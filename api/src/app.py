import json
import pathlib
from ipaddress import IPv4Address, IPv6Address
from typing import Any, cast

import click
from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_smorest import Api
from werkzeug.middleware.proxy_fix import ProxyFix

from src.config import require_secret_key, select_config
from src.extensions import init_db
from src.routes import register_blueprints

API_VERSION = "1.0.0"
OPENAPI_URL_PREFIX = "/api/v1"

API_SPEC_OPTIONS: dict[str, Any] = {
    "servers": [{"url": "/", "description": "current host"}],
    "components": {
        "responses": {
            "BadRequest": {
                "description": "Bad request: malformed input.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                },
            },
            "NotFound": {
                "description": "The requested resource was not found.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                },
            },
            "UnprocessableEntity": {
                "description": "Request validation failed.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                },
            },
        },
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
    },
}


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
    app.config["API_VERSION"] = API_VERSION
    app.config["OPENAPI_VERSION"] = "3.1.0"
    app.config["OPENAPI_URL_PREFIX"] = OPENAPI_URL_PREFIX
    app.config["OPENAPI_JSON_PATH"] = "openapi.json"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "/static/swagger-ui/"
    app.config["OPENAPI_REDOC_PATH"] = "/redoc"
    app.config["OPENAPI_REDOC_URL"] = "/static/redoc/redoc.standalone.js"
    app.config["OPENAPI_SWAGGER_UI_CONFIG"] = {"persistAuthorization": True}
    app.config["API_SPEC_OPTIONS"] = API_SPEC_OPTIONS


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
        registered.
    """
    app = Flask(__name__, static_folder="../static")
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

    _register_openapi_cli(app, smorest_api)

    return app


def _register_openapi_cli(app: Flask, smorest_api: Api) -> None:
    """Register `flask openapi-dump`: write the spec with deterministic
    formatting (sort_keys=True, trailing newline) and top-level `servers`
    stripped so generated TS clients stay host-agnostic.
    """

    @app.cli.command("openapi-dump")
    @click.option(
        "--output",
        "-o",
        default="openapi.json",
        type=click.Path(dir_okay=False, writable=True),
        show_default=True,
        help="Path to write the spec to (relative to CWD).",
    )
    def openapi_dump(output: str) -> None:  # pyright: ignore[reportUnusedFunction]
        spec_obj = smorest_api.spec
        assert spec_obj is not None, "flask-smorest spec not initialised"
        spec = cast(dict[str, Any], spec_obj.to_dict())
        spec.pop("servers", None)
        path = pathlib.Path(output)
        path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
        click.echo(f"wrote {path}")
