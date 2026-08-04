"""App-layer security headers.

Proxy already sets these in production. Keeping it for local debug.
"""

from __future__ import annotations

from flask import Flask, Response, request


def init_security_headers(app: Flask) -> None:
    # CSP and HSTS owned by nginx .
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
