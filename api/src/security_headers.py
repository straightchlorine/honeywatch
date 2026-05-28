"""App-layer security headers (defense in depth behind nginx).

nginx already sets these in production, but the api container may be hit
directly during ``just dev`` / local debug. Talisman would also work; a
small ``after_request`` hook keeps the dep surface minimal.
"""

from __future__ import annotations

from flask import Flask, Response


def init_security_headers(app: Flask) -> None:
    @app.after_request
    def _set_headers(response: Response) -> Response:  # pyright: ignore[reportUnusedFunction]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        # OpenAPI spec should not be cached in shared caches; the dashboard
        # regenerates clients off the freshest spec at dev time.
        if response.mimetype == "application/json":
            response.headers.setdefault("Cache-Control", "no-store")
        return response
