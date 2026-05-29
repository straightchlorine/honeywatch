import json
from typing import Any


def test_list_sessions(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    data = response.get_json()
    assert "items" in data
    assert "meta" in data
    assert data["meta"]["total"] == 2
    assert len(data["items"]) == 2


def test_list_sessions_no_src_ip_leak(client: Any, seed_data: Any) -> None:
    """Privacy contract: ``src_ip`` must never appear in list responses."""
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert b"src_ip" not in response.data
    for s in response.get_json()["items"]:
        assert "src_ip" not in s
        assert "country_code" in s
        assert "country" in s


def test_get_session_not_found(client: Any) -> None:
    response = client.get("/api/v1/sessions/nonexistent")
    assert response.status_code == 404
    data = response.get_json()
    # flask_smorest abort(404, message=...) produces {code, status, message}
    assert "message" in data or "errors" in data


def test_get_session_detail_with_seed_id(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/sessions/sess-001")
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == "sess-001"
    assert "src_ip" not in body


def test_get_session_malformed_id(client: Any) -> None:
    response = client.get("/api/v1/sessions/..%2F..%2Fetc")
    assert response.status_code in (404, 422)


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

    response = client.get("/api/v1/sessions/sessAAA001")
    assert response.status_code == 200
    assert b"src_ip" not in response.data
    body = response.get_json()
    assert "src_ip" not in body
    assert "country_code" in body
    assert "country" in body


def test_per_page_is_capped(client: Any, seed_data: Any) -> None:
    # per_page > 100 fails marshmallow validate.Range(max=100), surfacing 422
    response = client.get("/api/v1/sessions/?per_page=99999")
    assert response.status_code == 422


def test_sessions_invalid_page_returns_422(client: Any) -> None:
    response = client.get("/api/v1/sessions/?page=abc")
    assert response.status_code == 422
    data = response.get_json()
    assert "errors" in data or "code" in data


def test_sessions_invalid_session_id_returns_422(client: Any) -> None:
    response = client.get("/api/v1/sessions/!!!")
    assert response.status_code == 422


def test_sessions_unknown_session_id_returns_404(client: Any) -> None:
    response = client.get("/api/v1/sessions/aaaaaaaa")
    assert response.status_code == 404
    data = response.get_json()
    blob = (data.get("message") or "") + json.dumps(data)
    assert "Session" in blob or "aaaaaaaa" in blob


def test_session_detail_geo_enriched(client: Any, seed_data: Any) -> None:
    """A geo-enriched session exposes country/country_code, never src_ip.

    Exercises the populated GeoLocation join branch (seed gives sess-001 a US
    geo row) that the privacy gate would otherwise never cover.
    """
    del seed_data
    response = client.get("/api/v1/sessions/sess-001")
    assert response.status_code == 200
    assert b"src_ip" not in response.data
    body = response.get_json()
    assert body["country"] == "United States"
    assert body["country_code"] == "US"
    assert "src_ip" not in body
