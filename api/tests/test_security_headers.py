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


def test_cached_stats_endpoint_sets_max_age(client: Any) -> None:
    response = client.get("/api/v1/stats/auth-outcomes")
    assert response.status_code == 200
    assert "max-age=120" in response.headers.get("Cache-Control", "")


def test_cached_stats_endpoint_error_stays_no_store(
    app: Any, client: Any, monkeypatch: Any
) -> None:
    """An error must not inherit the endpoint's cache header.

    nginx honours upstream Cache-Control and its cache is shared by every
    viewer, so a cached 500 would be replayed to all of them until it expired.
    """
    from src.services.stats import credentials

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("simulated service failure")

    monkeypatch.setattr(credentials, "auth_outcomes", _boom)
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)

    response = client.get("/api/v1/stats/auth-outcomes")
    assert response.status_code == 500
    assert "no-store" in response.headers.get("Cache-Control", "")
