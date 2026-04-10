from typing import Any


def test_list_sessions_requires_auth(client: Any) -> None:
    response = client.get("/api/sessions")
    assert response.status_code == 401


def test_list_sessions(
    client: Any, auth_headers: dict[str, str], seed_data: Any
) -> None:
    response = client.get("/api/sessions", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert "sessions" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["sessions"]) == 2


def test_get_session_detail(
    client: Any, auth_headers: dict[str, str], seed_data: Any
) -> None:
    response = client.get("/api/sessions/sess-001", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == "sess-001"
    assert data["src_ip"] == "192.168.1.100"
    assert len(data["auth_attempts"]) == 2
    assert len(data["commands"]) == 1
    assert len(data["downloads"]) == 1


def test_get_session_not_found(client: Any, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/sessions/nonexistent", headers=auth_headers)
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_stats(client: Any, auth_headers: dict[str, str], seed_data: Any) -> None:
    response = client.get("/api/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_sessions"] == 2
    assert data["total_auth_attempts"] == 3
    assert data["unique_ips"] == 2
    assert len(data["top_usernames"]) > 0
    assert len(data["top_passwords"]) > 0
    assert isinstance(data["attacks_per_day"], list)
