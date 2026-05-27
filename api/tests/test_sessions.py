from typing import Any


def test_list_sessions(client: Any, seed_data: Any) -> None:
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.get_json()
    assert "sessions" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["sessions"]) == 2


def test_list_sessions_no_src_ip_leak(client: Any, seed_data: Any) -> None:
    """Privacy contract: ``src_ip`` must never appear in list responses."""
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert b"src_ip" not in response.data
    for s in response.get_json()["sessions"]:
        assert "src_ip" not in s
        assert "country_code" in s
        assert "country" in s


def test_get_session_not_found(client: Any) -> None:
    response = client.get("/api/sessions/nonexistent")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_get_session_detail_with_seed_id(client: Any, seed_data: Any) -> None:
    # "sess-001" contains a hyphen which the validator rejects; this asserts
    # the security contract rather than the historical shape.
    response = client.get("/api/sessions/sess-001")
    assert response.status_code == 400


def test_get_session_malformed_id(client: Any) -> None:
    response = client.get("/api/sessions/..%2F..%2Fetc")
    assert response.status_code in (400, 404)


def test_session_detail_no_src_ip_leak(
    client: Any, seed_data: Any, db_session: Any
) -> None:
    """Privacy contract: ``src_ip`` must never appear in detail responses.

    Seeded ids contain hyphens (rejected by the route's regex), so we insert a
    matching-pattern session for this assertion.
    """
    from datetime import datetime, timezone

    from src.models.session import Session as HoneypotSession

    db_session.add(
        HoneypotSession(
            id="sessAAA001",
            src_ip="203.0.113.7",
            src_port=44444,
            dst_port=22,
            protocol="ssh",
            started_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    response = client.get("/api/sessions/sessAAA001")
    assert response.status_code == 200
    assert b"src_ip" not in response.data
    body = response.get_json()
    assert "src_ip" not in body
    assert "country_code" in body
    assert "country" in body


def test_per_page_is_capped(client: Any, seed_data: Any) -> None:
    response = client.get("/api/sessions?per_page=99999")
    assert response.status_code == 200
    data = response.get_json()
    assert data["per_page"] == 100


def test_pagination_rejects_non_integer_page(client: Any, seed_data: Any) -> None:
    response = client.get("/api/sessions?page=abc")
    assert response.status_code == 200
    data = response.get_json()
    assert data["page"] == 1


def test_pagination_rejects_non_integer_per_page(client: Any, seed_data: Any) -> None:
    response = client.get("/api/sessions?per_page=xyz")
    assert response.status_code == 200
    data = response.get_json()
    assert data["per_page"] == 20
