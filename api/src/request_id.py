"""Request correlation id.

Reuses an inbound X-Request-Id or mints a UUID4, publishes it on `g.request_id`
for the log filter, and echoes it on the response. The inbound value is
attacker-controlled, hence the length cap and character strip.
"""

from __future__ import annotations

import re
from uuid import uuid4

from flask import Flask, Response, g, request

_SAFE_ID = re.compile(r"[^A-Za-z0-9\-]")
_MAX_LEN = 64


def _sanitize(value: str) -> str:
    return _SAFE_ID.sub("", value)[:_MAX_LEN]


def init_request_id(app: Flask) -> None:
    @app.before_request
    def _assign_request_id() -> None:  # pyright: ignore[reportUnusedFunction]
        inbound = request.headers.get("X-Request-Id", "").strip()
        cleaned = _sanitize(inbound) if inbound else ""
        g.request_id = cleaned or uuid4().hex

    @app.after_request
    def _echo_request_id(response: Response) -> Response:  # pyright: ignore[reportUnusedFunction]
        rid = getattr(g, "request_id", None)
        if rid:
            response.headers.setdefault("X-Request-Id", rid)
        return response
