from __future__ import annotations

import json
import pathlib
from typing import Any, cast

from flask import Flask
from flask_smorest import Api
from werkzeug.middleware.proxy_fix import ProxyFix

from src.config import (
    current_env,
    require_db_password,
    require_secret_key,
    select_config,
)
from src.error_handlers import init_error_handlers
from src.extensions import init_db
from src.logging_config import configure_logging
from src.openapi_cli import build_spec_dict, register_openapi_cli
from src.request_id import init_request_id
from src.routes import register_blueprints
from src.security_headers import init_security_headers

API_VERSION = "1.0.0"
API_V1_PREFIX = "/api/v1"
OPENAPI_URL_PREFIX = API_V1_PREFIX
STATIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "static"

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
            "InternalServerError": {
                "description": "An unexpected server error occurred.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                },
            },
        },
    },
}


def _configure_openapi(app: Flask) -> None:
    """Set flask-smorest config keys driving the spec + bundled UIs.

    Swagger UI / ReDoc assets are served from ``/static/*`` (committed under
    ``api/static/``) so the docs pages do not fetch JS from a CDN — keeps the
    OpenAPI surface working offline and behind tight CSP.
    """
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

    Order matters: ``configure_logging`` runs BEFORE ``Flask(__name__)`` so
    Flask's default handler is never attached and INFO-level records survive
    under gunicorn.
    """
    configure_logging()

    app = Flask(__name__, static_folder=str(STATIC_DIR))
    # nginx terminates TLS and forwards Host; x_host=1 lets url_for(_external=True)
    # produce correct absolute URLs. x_for=1, x_proto=1 match a single proxy hop.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # pyright: ignore[reportAttributeAccessIssue]

    if config is None:
        config = select_config()
    app.config.from_object(config)

    app.config["MAX_CONTENT_LENGTH"] = 8192
    app.config["SECRET_KEY"] = require_secret_key()

    if not app.config.get("TESTING"):
        require_db_password()

    _configure_openapi(app)
    smorest_api = Api(app)

    db_url = cast(
        str,
        app.config.get("SQLALCHEMY_DATABASE_URI") or "",  # pyright: ignore[reportUnknownMemberType]
    )
    if db_url:
        init_db(app, db_url)
    else:
        app.logger.warning(
            "SQLALCHEMY_DATABASE_URI is empty; database not initialized - "
            "data routes will fail until it is configured"
        )

    init_request_id(app)
    init_security_headers(app)
    init_error_handlers(app)
    register_blueprints(smorest_api)
    _install_openapi_cache(app, smorest_api)
    register_openapi_cli(app, smorest_api)

    app.logger.info(
        "honeywatch api %s starting (env=%s, db=%s)",
        API_VERSION,
        current_env(),
        "on" if db_url else "OFF",
    )
    return app


def _install_openapi_cache(app: Flask, smorest_api: Api) -> None:
    """Override smorest's openapi.json view with a startup-cached body.

    flask-smorest rebuilds ``spec.to_dict()`` on every GET; for our spec that
    is wasted CPU per request. We materialise the JSON once after blueprint
    registration and return the cached bytes via a thin view function.
    """
    try:
        spec = build_spec_dict(smorest_api)
    except RuntimeError:
        app.logger.warning(
            "openapi spec unavailable at boot; serving smorest's per-request spec"
        )
        return
    body = json.dumps(spec)
    endpoint = "api-docs.openapi_json"

    def _cached_openapi() -> tuple[str, int, dict[str, str]]:
        return body, 200, {"Content-Type": "application/json"}

    app.view_functions[endpoint] = _cached_openapi
