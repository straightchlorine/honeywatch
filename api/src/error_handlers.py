"""JSON error handlers matching the flask-smorest ``Error`` envelope.

* Return the same JSON shape on every layer (``{code, status, message, errors}``).
* Log 5xx with ``exc_info`` plus request context.
* Log 4xx at INFO with path + remote_addr so we can see scanning / bad clients.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


def _envelope(
    code: int, status: str, message: str, errors: Any = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "status": status, "message": message}
    if errors is not None:
        body["errors"] = errors
    return body


def init_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _on_http(exc: HTTPException) -> Any:  # pyright: ignore[reportUnusedFunction]
        code = exc.code or 500
        status = exc.name or "Error"
        message = exc.description or status
        body = getattr(exc, "data", None) or {}
        # flask-smorest stuffs marshmallow validation messages under
        # ``exc.data['errors']``; preserve that shape.
        errors = body.get("errors") if isinstance(body, dict) else None
        # smorest also passes its own ``message`` field via ``exc.data``.
        if isinstance(body, dict) and isinstance(body.get("message"), str):
            message = body["message"]

        if code >= 500:
            current_app.logger.exception(
                "http %s on %s %s", code, request.method, request.path
            )
        else:
            current_app.logger.info(
                "http %s on %s %s remote=%s",
                code,
                request.method,
                request.path,
                request.remote_addr,
            )
        return jsonify(_envelope(code, status, message, errors)), code

    @app.errorhandler(Exception)
    def _on_unhandled(exc: Exception) -> Any:  # pyright: ignore[reportUnusedFunction]
        # Re-raise HTTPException so the dedicated handler above runs (Flask's
        # registry calls the most specific handler, but this guard is cheap).
        if isinstance(exc, HTTPException):
            raise exc
        current_app.logger.exception(
            "unhandled exception on %s %s", request.method, request.path
        )
        return (
            jsonify(
                _envelope(
                    500,
                    "Internal Server Error",
                    "An internal error occurred.",
                )
            ),
            500,
        )
