from typing import Any


def test_health_returns_ok(client: Any) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_health_no_auth_required(client: Any) -> None:
    response = client.get("/health")
    assert response.status_code == 200
