"""App-layer security headers (defense in depth behind nginx)."""

from __future__ import annotations

from typing import Any


def test_security_headers_present_on_health(client: Any) -> None:
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in response.headers


def test_openapi_json_uses_no_store(client: Any) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")
