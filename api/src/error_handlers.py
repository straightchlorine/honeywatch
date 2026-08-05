"""JSON error handlers matching the flask-smorest Error envelope.

Every failure, whatever raised it, comes back as
`{code, status, message, errors}` so clients parse one shape.

Log lines never include request.remote_addr: attacker IPs stay out of the logs.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, current_app, jsonify, request
from werkzeug.exceptions import HTTPException


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
        # flask-smorest passes marshmallow validation output through exc.data;
        # keep its errors/message rather than the generic HTTP description.
        body = getattr(exc, "data", None) or {}
        errors = body.get("errors") if isinstance(body, dict) else None
        if isinstance(body, dict) and isinstance(body.get("message"), str):
            message = body["message"]

        if code >= 500:
            current_app.logger.exception(
                "http %s on %s %s", code, request.method, request.path
            )
        else:
            current_app.logger.info(
                "http %s on %s %s", code, request.method, request.path
            )
        return jsonify(_envelope(code, status, message, errors)), code

    @app.errorhandler(Exception)
    def _on_unhandled(exc: Exception) -> Any:  # pyright: ignore[reportUnusedFunction]
        # Re-raise HTTPException so the dedicated handler above runs
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
