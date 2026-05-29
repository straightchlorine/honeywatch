"""App-layer security headers (defense in depth behind nginx).

nginx already sets these in production, but the api container may be hit
directly during ``just dev`` / local debug. Talisman would also work; a
small ``after_request`` hook keeps the dep surface minimal.
"""

from __future__ import annotations

from flask import Flask, Response, request


def init_security_headers(app: Flask) -> None:
    # NOTE: CSP and HSTS are owned by nginx (TLS/edge concerns).
    # Not set here, to avoid a duplicate/conflicting in-app policy.
    @app.after_request
    def _set_headers(response: Response) -> Response:  # pyright: ignore[reportUnusedFunction]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        if response.mimetype == "application/json":
            # The OpenAPI spec and error responses must not be cached.
            if request.path.endswith("/openapi.json") or response.status_code >= 400:
                response.headers.setdefault("Cache-Control", "no-store")
            else:
                response.headers.setdefault("Cache-Control", "public, max-age=30")
        return response
