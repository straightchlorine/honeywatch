from typing import Any

import pytest
from sqlalchemy.exc import OperationalError


def test_health_returns_ok(client: Any) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_ready_returns_ok_when_db_up(client: Any) -> None:
    """`/health/ready` round-trips a SELECT 1 to the test database."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ready"


def test_ready_returns_503_when_db_down(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing DB session yields 503 with a reason, not a 500 traceback."""

    def _explode(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError(
            "simulated outage", params=None, orig=Exception("connection refused")
        )

    # Patch the routes-layer reference (Python imports it by name at module
    # load), not the symbol in src.extensions, so our route picks up the
    # exploding factory rather than the real one wired by the `client` fixture.
    monkeypatch.setattr("src.routes.health.get_session_factory", _explode)

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.get_json()
    assert data["status"] == "unavailable"
    assert data["reason"] == "db"
