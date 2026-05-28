"""Request id middleware: echo inbound, mint when missing, sanitize hostile."""

from __future__ import annotations

import re
from typing import Any


def test_request_id_minted_when_missing(client: Any) -> None:
    response = client.get("/health")
    rid = response.headers.get("X-Request-Id")
    assert rid is not None
    assert re.fullmatch(r"[A-Fa-f0-9]{32}", rid), rid


def test_request_id_echoed_when_present(client: Any) -> None:
    response = client.get("/health", headers={"X-Request-Id": "abc-123"})
    assert response.headers["X-Request-Id"] == "abc-123"


def test_request_id_sanitized(client: Any) -> None:
    """Hostile inbound: brackets, quotes, spaces, slashes get stripped."""
    response = client.get("/health", headers={"X-Request-Id": "a b<script>c/d"})
    rid = response.headers["X-Request-Id"]
    assert "<" not in rid
    assert " " not in rid
    assert "/" not in rid
    assert rid == "abscriptcd"


def test_request_id_length_capped(client: Any) -> None:
    response = client.get("/health", headers={"X-Request-Id": "a" * 200})
    assert len(response.headers["X-Request-Id"]) <= 64
