"""App-layer security headers.

nginx sets these in production; these are the fallback for running the app
directly. setdefault everywhere, so the proxy's values always win.
"""

from __future__ import annotations

from flask import Flask, Response, request


def init_security_headers(app: Flask) -> None:
    # CSP and HSTS are nginx-only: both need the deployed origin to be right.
    @app.after_request
    def _set_headers(response: Response) -> Response:  # pyright: ignore[reportUnusedFunction]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        if response.mimetype == "application/json":
            # Stats tolerate 30s of staleness; a cached spec or error does not.
            if request.path.endswith("/openapi.json") or response.status_code >= 400:
                response.headers.setdefault("Cache-Control", "no-store")
            else:
                response.headers.setdefault("Cache-Control", "public, max-age=30")
        return response
