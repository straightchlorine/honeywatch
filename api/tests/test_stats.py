from datetime import datetime, timedelta, timezone
from typing import Any

from src.models.auth_attempt import AuthAttempt
from src.models.direct_tcpip import DirectTcpipRequest
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session as HoneypotSession
from tests.conftest import LONG_PASSWORD


def test_totals(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/stats/totals")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_sessions"] == 2
    assert data["total_auth_attempts"] == 3
    assert data["unique_ips"] == 2


def test_top_passwords(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/stats/top-passwords")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    counts = [row["count"] for row in data]
    assert counts == sorted(counts, reverse=True)


def test_top_passwords_top_n_clamp(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/stats/top-passwords?top_n=1")
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def test_top_countries_buckets_missing_geo_as_unknown(
    client: Any, seed_data: Any
) -> None:
    """Outer join + COALESCE bucket sessions without geo rows as Unknown to avoid
    undercounting."""
    response = client.get("/api/v1/stats/top-countries")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(
        row["country"] == "Unknown"
        and row["country_code"] == "??"
        and row["count"] >= 1
        for row in data
    ), data


def test_activity_each_bucket(client: Any, seed_data: Any) -> None:
    for bucket in ("hour", "day", "month"):
        response = client.get(f"/api/v1/stats/activity?bucket={bucket}")
        assert response.status_code == 200, bucket
        data = response.get_json()
        assert isinstance(data, list)
        for row in data:
            assert "bucket" in row
            assert "count" in row


def test_activity_invalid_bucket(client: Any) -> None:
    response = client.get("/api/v1/stats/activity?bucket=fortnight")
    assert response.status_code == 422
    data = response.get_json()
    assert "errors" in data or "code" in data


def test_activity_default_bucket_is_day(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/stats/activity")
    assert response.status_code == 200


def test_trend_default(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/stats/trend")
    assert response.status_code == 200
    data = response.get_json()
    assert set(data.keys()) == {"current", "previous", "delta", "pct_change"}


def test_trend_zero_previous_returns_null_pct(client: Any, db_session: Any) -> None:
    """`pct_change` is `None` when the prior window has no sessions."""
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id="recentAAA1",
            src_ip="198.51.100.1",
            src_port=11111,
            dst_port=22,
            protocol="ssh",
            started_at=now - timedelta(days=1),
        )
    )
    db_session.flush()

    response = client.get("/api/v1/stats/trend?period_days=3")
    assert response.status_code == 200
    data = response.get_json()
    assert data["current"] == 1
    assert data["previous"] == 0
    assert data["delta"] == 1
    assert data["pct_change"] is None


def test_trend_period_days_clamped(client: Any) -> None:
    response = client.get("/api/v1/stats/trend?period_days=99999")
    assert response.status_code == 422


def test_heatmap(client: Any, seed_data: Any) -> None:
    response = client.get("/api/v1/stats/heatmap")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    for row in data:
        assert set(row.keys()) == {"hour", "weekday", "count"}
        assert 0 <= row["hour"] <= 23
        assert 0 <= row["weekday"] <= 6


def test_top_countries_includes_geo_enriched(client: Any, seed_data: Any) -> None:
    """The populated geo branch surfaces the enriched country (US), not Unknown."""
    del seed_data
    response = client.get("/api/v1/stats/top-countries")
    assert response.status_code == 200
    data = response.get_json()
    assert any(
        row["country"] == "United States" and row["country_code"] == "US"
        for row in data
    ), data


def test_activity_country_filter(client: Any, seed_data: Any) -> None:
    """Only sess-001 is geo-enriched (US); the timeline scopes to it."""
    del seed_data
    response = client.get("/api/v1/stats/activity?bucket=day&country=US")
    assert response.status_code == 200
    assert sum(row["count"] for row in response.get_json()) == 1


def test_heatmap_country_filter(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/heatmap?country=US")
    assert response.status_code == 200
    assert sum(row["count"] for row in response.get_json()) == 1


def test_trend_country_filter(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/trend?country=US")
    assert response.status_code == 200
    assert response.get_json()["current"] == 1


def test_stats_country_filter_unknown_country_is_empty(
    client: Any, seed_data: Any
) -> None:
    del seed_data
    response = client.get("/api/v1/stats/activity?bucket=day&country=ZZ")
    assert response.status_code == 200
    assert sum(row["count"] for row in response.get_json()) == 0


def test_stats_country_filter_rejects_invalid(client: Any) -> None:
    assert (
        client.get("/api/v1/stats/activity?bucket=day&country=USA").status_code == 422
    )
    assert client.get("/api/v1/stats/heatmap?country=1").status_code == 422


def test_top_credentials_pairs_default(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/top-credentials")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert {(r["username"], r["password"]) for r in data} == {
        ("root", "password123"),
        ("admin", "admin"),
        ("root", "toor"),
    }
    counts = [r["count"] for r in data]
    assert counts == sorted(counts, reverse=True)
    assert all(r["distinct_ips"] is None for r in data)


def test_top_credentials_by_username(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?by=username")
    assert response.status_code == 200
    data = response.get_json()
    assert all(r["password"] is None for r in data)
    by_user = {r["username"]: r["count"] for r in data}
    assert by_user == {"root": 2, "admin": 1}
    assert data[0]["username"] == "root"


def test_top_credentials_by_password(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?by=password")
    assert response.status_code == 200
    data = response.get_json()
    assert all(r["username"] is None for r in data)
    assert {r["password"] for r in data} == {"password123", "admin", "toor"}


def test_top_credentials_success_only(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?outcome=success")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["username"] == "root"
    assert data[0]["password"] == "toor"


def test_top_credentials_ip_fanout_metric(client: Any, seed_data: Any) -> None:
    """ip_fanout populates distinct_ips (the distributed-botnet discriminator)."""
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?metric=ip_fanout")
    assert response.status_code == 200
    data = response.get_json()
    assert data, data
    assert all(isinstance(r["distinct_ips"], int) for r in data)
    assert all(r["distinct_ips"] == 1 for r in data)


def test_top_credentials_ip_fanout_ranks_distributed_pair_first(
    client: Any, ip_fanout_seed: Any
) -> None:
    """A pair tried from two IPs reports distinct_ips==2 and outranks a 1-IP pair.

    ip_fanout is the discriminator between a distributed botnet sharing a
    hardcoded credential table and a lone brute-forcer; the multi-IP pair must
    sort above the single-IP one.
    """
    del ip_fanout_seed
    response = client.get("/api/v1/stats/top-credentials?metric=ip_fanout")
    assert response.status_code == 200
    data = response.get_json()
    fanout = {(r["username"], r["password"]): r["distinct_ips"] for r in data}
    assert fanout[("botnet", "sharedpw")] == 2
    assert fanout[("loner", "lonelypw")] == 1
    # the distributed pair ranks strictly above the single-IP one.
    order = [(r["username"], r["password"]) for r in data]
    assert order.index(("botnet", "sharedpw")) < order.index(("loner", "lonelypw"))


def test_top_credentials_top_n_clamp(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?top_n=1")
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def test_top_credentials_rejects_invalid_params(client: Any) -> None:
    assert client.get("/api/v1/stats/top-credentials?by=bogus").status_code == 422
    assert client.get("/api/v1/stats/top-credentials?metric=bogus").status_code == 422
    assert client.get("/api/v1/stats/top-credentials?outcome=bogus").status_code == 422


def test_auth_outcomes(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/auth-outcomes")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 3
    assert data["successful"] == 1
    assert data["failed"] == 2
    assert data["success_rate"] == round(1 / 3 * 100, 2)
    # seed passwords: password123, admin, toor -> 3 distinct.
    assert data["unique_passwords"] == 3
    # seed usernames: root, admin, root -> 2 distinct.
    assert data["unique_usernames"] == 2


def test_auth_outcomes_empty_returns_null_rate(client: Any, db_session: Any) -> None:
    """No attempts -> success_rate is null (no divide-by-zero)."""
    del db_session
    response = client.get("/api/v1/stats/auth-outcomes")
    assert response.status_code == 200
    data = response.get_json()
    assert data == {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "success_rate": None,
        "unique_passwords": 0,
        "unique_usernames": 0,
    }


def _outcome_session(
    db_session: Any,
    sid: str,
    ip: str,
    *,
    n_commands: int = 0,
    n_downloads: int = 0,
    n_tcpip: int = 0,
    auth_success: bool = False,
    country_code: str | None = None,
) -> None:
    """Seed session with ingestor-maintained outcome counters (not derived from
    child rows)."""
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id=sid,
            src_ip=ip,
            src_port=1,
            dst_port=22,
            protocol="ssh",
            started_at=now,
            n_commands=n_commands,
            n_downloads=n_downloads,
            n_tcpip=n_tcpip,
            auth_success=auth_success,
        )
    )
    db_session.flush()
    if country_code is not None:
        db_session.add(GeoLocation(ip=ip, country_code=country_code))
        db_session.flush()


def test_outcomes_keys_and_types(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/outcomes")
    assert response.status_code == 200
    data = response.get_json()
    assert set(data.keys()) == {
        "shell",
        "commands",
        "tcpip",
        "downloads",
        "none",
        "total",
    }
    assert all(isinstance(v, int) for v in data.values())


def test_outcomes_buckets_overlap_and_none_is_complement(
    client: Any, db_session: Any
) -> None:
    """Buckets overlap - a session can count in both `shell` and `commands` -
    so a naive sum-to-total implementation must fail this test. `none` is
    exactly the sessions with none of the other four, not `total` minus
    their sum.
    """
    # Both shell and commands on one session - exercises the overlap.
    _outcome_session(
        db_session, "out-both", "203.0.113.1", n_commands=2, auth_success=True
    )
    _outcome_session(db_session, "out-shell", "203.0.113.2", auth_success=True)
    _outcome_session(db_session, "out-download", "203.0.113.3", n_downloads=1)
    _outcome_session(db_session, "out-tcpip", "203.0.113.4", n_tcpip=2)
    _outcome_session(db_session, "out-none", "203.0.113.5")
    db_session.commit()

    data = client.get("/api/v1/stats/outcomes").get_json()
    assert data["shell"] == 2  # out-both, out-shell
    assert data["commands"] == 1  # out-both
    assert data["downloads"] == 1  # out-download
    assert data["tcpip"] == 1  # out-tcpip
    assert data["none"] == 1  # out-none only
    assert data["total"] == 5
    # Overlap proof: the four activity buckets sum to MORE than the number of
    # sessions that had any activity at all, because out-both is counted twice.
    # Comparing against `total` would not prove it - the idle session drags the
    # total back up to the sum by coincidence.
    overlap_sum = data["shell"] + data["commands"] + data["downloads"] + data["tcpip"]
    assert overlap_sum > data["total"] - data["none"]


def test_outcomes_country_narrows_every_bucket(client: Any, db_session: Any) -> None:
    _outcome_session(
        db_session,
        "out-us-both",
        "203.0.113.11",
        n_commands=1,
        auth_success=True,
        country_code="US",
    )
    _outcome_session(
        db_session,
        "out-us-download",
        "203.0.113.12",
        n_downloads=1,
        country_code="US",
    )
    _outcome_session(
        db_session,
        "out-de-shell",
        "203.0.113.13",
        auth_success=True,
        country_code="DE",
    )
    db_session.commit()

    data = client.get("/api/v1/stats/outcomes?country=US").get_json()
    assert data["shell"] == 1
    assert data["commands"] == 1
    assert data["downloads"] == 1
    assert data["tcpip"] == 0
    assert data["none"] == 0
    assert data["total"] == 2  # the DE session is excluded


def test_outcomes_unknown_country_is_all_zero(client: Any, seed_data: Any) -> None:
    """A country with no matching sessions returns all-zero counts, not a 404 -
    the aggregate query always yields exactly one row."""
    del seed_data
    response = client.get("/api/v1/stats/outcomes?country=ZZ")
    assert response.status_code == 200
    assert response.get_json() == {
        "shell": 0,
        "commands": 0,
        "tcpip": 0,
        "downloads": 0,
        "none": 0,
        "total": 0,
    }


def test_outcomes_rejects_invalid_country(client: Any) -> None:
    assert client.get("/api/v1/stats/outcomes?country=USA").status_code == 422


def _country_row(data: dict[str, Any], code: str) -> dict[str, Any]:
    """Pluck one country row from the leaderboard envelope by code."""
    matches = [r for r in data["countries"] if r["country_code"] == code]
    assert matches, f"{code} missing from {data['countries']}"
    return matches[0]


def test_countries_breakdown_envelope(client: Any, seed_data: Any) -> None:
    """The leaderboard carries per-country rows plus the geo-coverage header.

    Seed: session1 (US, 2 failed attempts) + session2 (geo-less -> Unknown, 1
    accepted attempt). Only US is geo-resolved, so 1 of 2 sessions has geo.
    """
    del seed_data
    response = client.get("/api/v1/stats/countries")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_countries"] == 1  # US only; the ?? bucket is not a country
    assert data["geo_resolved_pct"] == 50.0  # 1 of 2 sessions enriched

    us = _country_row(data, "US")
    assert us["country"] == "United States"
    assert us["sessions"] == 1
    assert us["distinct_ips"] == 1
    assert us["attempts"] == 2
    assert us["successful"] == 0
    assert us["success_rate"] == 0.0
    assert us["distinct_usernames"] == 2  # root, admin
    assert us["distinct_passwords"] == 2  # password123, admin

    unknown = _country_row(data, "??")
    assert unknown["country"] == "Unknown"
    assert unknown["sessions"] == 1
    assert unknown["attempts"] == 1
    assert unknown["successful"] == 1
    assert unknown["success_rate"] == 100.0


def test_countries_session_grain_not_inflated_by_attempts(
    client: Any, seed_data: Any
) -> None:
    """Joining auth_attempts must not multiply the session/IP counts.

    The US session has 2 auth attempts; a naive COUNT(*) would report 2
    sessions. COUNT(DISTINCT session) keeps it at 1 while attempts stays 2 --
    the core grain invariant of the mixed-grain query.
    """
    del seed_data
    data = client.get("/api/v1/stats/countries").get_json()
    us = _country_row(data, "US")
    assert us["sessions"] == 1 and us["distinct_ips"] == 1
    assert us["attempts"] == 2


def test_countries_sort_by_success_rate(client: Any, seed_data: Any) -> None:
    del seed_data
    data = client.get("/api/v1/stats/countries?sort=success_rate").get_json()
    order = [r["country_code"] for r in data["countries"]]
    assert order.index("??") < order.index("US")


def test_countries_sort_rejects_invalid(client: Any) -> None:
    assert client.get("/api/v1/stats/countries?sort=bogus").status_code == 422


def test_countries_order_rejects_invalid(client: Any) -> None:
    assert client.get("/api/v1/stats/countries?order=bogus").status_code == 422


def test_countries_order_asc_reverses_order_desc(client: Any, db_session: Any) -> None:
    """order=asc must reverse the default-desc ranking on the default sessions
    sort key, without touching sort= itself."""
    _add_session(
        db_session, "sess-aa-1", "192.0.2.20", country_code="AA", country="Aland"
    )
    _add_session(
        db_session, "sess-aa-2", "192.0.2.21", country_code="AA", country="Aland"
    )
    _add_session(
        db_session, "sess-bb-1", "192.0.2.22", country_code="BB", country="Bland"
    )
    desc_order = [
        r["country_code"]
        for r in client.get("/api/v1/stats/countries").get_json()["countries"]
    ]
    asc_order = [
        r["country_code"]
        for r in client.get("/api/v1/stats/countries?order=asc").get_json()["countries"]
    ]
    assert asc_order == list(reversed(desc_order))


def test_countries_top_n_clamp(client: Any, seed_data: Any) -> None:
    del seed_data
    data = client.get("/api/v1/stats/countries?top_n=1").get_json()
    assert len(data["countries"]) == 1


def test_countries_empty_geo_pct_is_null(client: Any, db_session: Any) -> None:
    """No sessions -> geo_resolved_pct is null (no divide-by-zero)."""
    del db_session
    data = client.get("/api/v1/stats/countries").get_json()
    assert data["countries"] == []
    assert data["total_countries"] == 0
    assert data["geo_resolved_pct"] is None


def test_asns_scoped_to_country(client: Any, seed_data: Any) -> None:
    del seed_data
    data = client.get("/api/v1/stats/asns?country=US").get_json()
    assert len(data) == 1
    row = data[0]
    assert row["asn"] == 14618
    assert row["as_org"] == "Example Org"
    assert row["sessions"] == 1
    assert row["distinct_ips"] == 1
    assert client.get("/api/v1/stats/asns?country=ZZ").get_json() == []


def test_asns_excludes_null_asn(client: Any, seed_data: Any) -> None:
    del seed_data
    data = client.get("/api/v1/stats/asns").get_json()
    assert [r["asn"] for r in data] == [14618]


def test_top_credentials_country_filter(client: Any, seed_data: Any) -> None:
    """country= scopes the credential dictionary to one origin.

    'toor' (the accepted password) belongs to the geo-less Unknown session, so
    it must not appear when scoping to US.
    """
    del seed_data
    data = client.get("/api/v1/stats/top-credentials?by=password&country=US").get_json()
    passwords = {r["password"] for r in data}
    assert passwords == {"password123", "admin"}
    assert "toor" not in passwords


def test_top_credentials_country_composes_with_ip_fanout(
    client: Any, seed_data: Any
) -> None:
    """country + ip_fanout must not double-join Session; distinct_ips still set."""
    del seed_data
    response = client.get(
        "/api/v1/stats/top-credentials?country=US&metric=ip_fanout&by=pair"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data, data
    assert all(r["distinct_ips"] == 1 for r in data)


def test_top_credentials_rejects_invalid_country(client: Any) -> None:
    assert client.get("/api/v1/stats/top-credentials?country=USA").status_code == 422


def test_top_credentials_unknown_bucket(client: Any, seed_data: Any) -> None:
    """country=?? scopes to the geo-less bucket (sess-002: root/toor).

    The US session's creds (password123, admin) belong to a resolved country, so
    they must be absent; only the no-geo session's accepted pair remains.
    """
    del seed_data
    data = client.get("/api/v1/stats/top-credentials?by=password&country=??").get_json()
    passwords = {r["password"] for r in data}
    assert passwords == {"toor"}
    usernames = {
        r["username"]
        for r in client.get(
            "/api/v1/stats/top-credentials?by=username&country=??"
        ).get_json()
    }
    assert usernames == {"root"}


def test_asns_unknown_bucket_empty_without_geo(client: Any, seed_data: Any) -> None:
    del seed_data
    assert client.get("/api/v1/stats/asns?country=??").get_json() == []


def test_strict_country_endpoints_reject_unknown_sentinel(client: Any) -> None:
    """Only the credential/ASN leaderboards accept '??'; activity stays strict."""
    assert client.get("/api/v1/stats/activity?bucket=day&country=??").status_code == 422
    assert client.get("/api/v1/stats/heatmap?country=??").status_code == 422


def _add_session(
    db_session: Any,
    sid: str,
    ip: str,
    *,
    country_code: str | None = None,
    country: str | None = None,
    asn: int | None = None,
    as_org: str | None = None,
    attempts: int = 0,
    successful: int = 0,
) -> None:
    """Seed session with optional geo row and auth attempts for edge cases."""
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id=sid,
            src_ip=ip,
            src_port=2222,
            dst_port=22,
            protocol="ssh",
            started_at=now,
            sensor="edge",
        )
    )
    db_session.flush()
    if country_code is not None or asn is not None:
        db_session.add(
            GeoLocation(
                ip=ip,
                country_code=country_code,
                country=country,
                asn=asn,
                as_org=as_org,
                last_updated=now,
            )
        )
    for i in range(attempts):
        db_session.add(
            AuthAttempt(
                session_id=sid,
                username="root",
                password=f"pw-{i}",
                success=i < successful,
                timestamp=now,
            )
        )
    db_session.flush()


def test_asns_unknown_bucket_includes_null_country_with_asn(
    client: Any, db_session: Any
) -> None:
    """country=?? surfaces a geo row that carries an ASN but no country_code.

    The MaxMind ASN-hit-without-city case: `country_code` NULL but `asn` set.
    It must appear in the ?? bucket (and the global list) yet stay out of any
    resolved-country scope.
    """
    _add_session(
        db_session,
        "sess-null-ctry",
        "203.0.113.5",
        asn=64500,
        as_org="Null-Country Net",
    )
    unknown = client.get("/api/v1/stats/asns?country=??").get_json()
    assert [(r["asn"], r["as_org"]) for r in unknown] == [(64500, "Null-Country Net")]
    # Present globally (asn is not null) but absent from a resolved-country scope.
    assert [r["asn"] for r in client.get("/api/v1/stats/asns").get_json()] == [64500]
    assert client.get("/api/v1/stats/asns?country=US").get_json() == []


def test_countries_total_countries_independent_of_top_n(
    client: Any, db_session: Any
) -> None:
    """total_countries counts every distinct country, not just the returned page.

    Three resolved countries seeded; ?top_n=1 returns one row but the header
    still reports 3 - proving the count is not derived from the truncated list.
    """
    for i, cc in enumerate(("US", "CN", "DE")):
        _add_session(
            db_session,
            f"sess-tc-{i}",
            f"198.51.100.{i + 1}",
            country_code=cc,
            country=cc,
            attempts=1,
        )
    data = client.get("/api/v1/stats/countries?top_n=1").get_json()
    assert len(data["countries"]) == 1
    assert data["total_countries"] == 3


def test_countries_success_rate_sort_puts_no_attempt_country_last(
    client: Any, db_session: Any
) -> None:
    """A country with sessions but zero auth attempts sorts last under
    success_rate (the COALESCE(-1) floor), not first, and its rate is null."""
    _add_session(
        db_session,
        "sess-aa",
        "198.51.100.10",
        country_code="AA",
        country="Aland",
        attempts=1,
        successful=1,
    )
    _add_session(
        db_session,
        "sess-zz",
        "198.51.100.11",
        country_code="ZZ",
        country="Zedland",
        attempts=0,
    )
    data = client.get("/api/v1/stats/countries?sort=success_rate").get_json()
    order = [r["country_code"] for r in data["countries"]]
    assert order[-1] == "ZZ"  # null rate floored to -1 -> last under DESC, not first
    assert order.index("AA") < order.index("ZZ")
    zz = _country_row(data, "ZZ")
    assert zz["success_rate"] is None
    assert zz["attempts"] == 0


def test_countries_success_rate_sort_order_asc_puts_no_attempt_country_last(
    client: Any, db_session: Any
) -> None:
    """nulls_last() must hold under order=asc too, not just the desc default -
    the no-attempt country stays last either way, and its rate is still null."""
    _add_session(
        db_session,
        "sess-aa",
        "198.51.100.10",
        country_code="AA",
        country="Aland",
        attempts=1,
        successful=1,
    )
    _add_session(
        db_session,
        "sess-zz",
        "198.51.100.11",
        country_code="ZZ",
        country="Zedland",
        attempts=0,
    )
    data = client.get("/api/v1/stats/countries?sort=success_rate&order=asc").get_json()
    order = [r["country_code"] for r in data["countries"]]
    assert order[-1] == "ZZ"
    zz = _country_row(data, "ZZ")
    assert zz["success_rate"] is None
    assert zz["attempts"] == 0


def test_country_filter_normalizes_lowercase(client: Any, seed_data: Any) -> None:
    del seed_data
    lower = client.get("/api/v1/stats/asns?country=us").get_json()
    upper = client.get("/api/v1/stats/asns?country=US").get_json()
    assert lower == upper
    assert [r["asn"] for r in lower] == [14618]


def test_strict_country_filter_normalizes_lowercase(
    client: Any, seed_data: Any
) -> None:
    del seed_data
    lower = client.get("/api/v1/stats/activity?bucket=day&country=us")
    assert lower.status_code == 200
    upper = client.get("/api/v1/stats/activity?bucket=day&country=US")
    assert lower.get_json() == upper.get_json()


def test_password_composition(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/password-composition")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 3
    assert data["capped_at"] == 16
    lengths = {row["length"]: row["count"] for row in data["lengths"]}
    assert lengths == {4: 1, 5: 1, 11: 1}
    classes = {row["name"]: row["count"] for row in data["classes"]}
    assert classes == {"lower": 2, "alnum": 1}
    assert data["classes"][0]["name"] == "lower"


def test_password_composition_charset_classes_cover_every_branch(
    client: Any, charset_seed: Any
) -> None:
    """Charset classification prioritizes by branch order (see conftest.py)."""
    del charset_seed
    response = client.get("/api/v1/stats/password-composition")
    assert response.status_code == 200
    classes = {row["name"]: row["count"] for row in response.get_json()["classes"]}
    assert classes == {
        "empty": 1,
        "symbol": 1,
        "digits": 1,
        "lower": 2,
        "upper": 1,
        "alnum": 1,
    }


def test_passwords_by_length_exact(client: Any, seed_data: Any) -> None:
    """An exact-length query returns only the passwords of that length."""
    del seed_data
    assert client.get("/api/v1/stats/passwords-by-length?length=5").get_json() == [
        {"password": "admin", "count": 1}
    ]
    assert client.get("/api/v1/stats/passwords-by-length?length=4").get_json() == [
        {"password": "toor", "count": 1}
    ]
    assert client.get("/api/v1/stats/passwords-by-length?length=11").get_json() == [
        {"password": "password123", "count": 1}
    ]


def test_passwords_by_length_no_match_is_empty(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/passwords-by-length?length=7")
    assert response.status_code == 200
    assert response.get_json() == []


def test_passwords_by_length_cap_is_inclusive_tail(
    client: Any, charset_seed: Any
) -> None:
    """At the cap (>= branch) the query lists every password that length or longer.

    `charset_seed` includes an 18-char password (> the cap of 16). Querying
    `length=16` must return it via the `length_col >= cap` tail branch, while
    a sub-cap exact query (`length=11`) must NOT - the 18-char row only
    matches the inclusive tail, not an exact-length lookup.
    """
    del charset_seed
    assert len(LONG_PASSWORD) >= 16
    tail = client.get("/api/v1/stats/passwords-by-length?length=16").get_json()
    assert {row["password"] for row in tail} == {LONG_PASSWORD}
    exact = client.get("/api/v1/stats/passwords-by-length?length=11").get_json()
    assert all(row["password"] != LONG_PASSWORD for row in exact)


def test_passwords_by_length_requires_length(client: Any) -> None:
    assert client.get("/api/v1/stats/passwords-by-length").status_code == 422


def test_passwords_by_length_rejects_out_of_range(client: Any) -> None:
    assert client.get("/api/v1/stats/passwords-by-length?length=-1").status_code == 422
    assert client.get("/api/v1/stats/passwords-by-length?length=99").status_code == 422


def test_downloads_name_is_url_basename_not_outfile(
    client: Any, db_session: Any
) -> None:
    """`name` derives from attacker URL, not honeypot storage path."""
    now = datetime.now(timezone.utc)
    sha256 = "f" * 64
    db_session.add(
        HoneypotSession(id="dl-001", src_ip="203.0.113.9", src_port=1, started_at=now)
    )
    db_session.flush()
    db_session.add_all(
        [
            Download(
                session_id="dl-001",
                url="http://cnc.example.com/meow",
                outfile=f"var/lib/cowrie/downloads/{sha256}",
                sha256=sha256,
                timestamp=now,
            ),
            Download(
                session_id="dl-001",
                url="http://cnc.example.com/meow",
                outfile=f"var/lib/cowrie/downloads/{sha256}",
                sha256=sha256,
                timestamp=now,
            ),
            Download(
                session_id="dl-001",
                url="http://other.example.com/other",
                outfile=f"var/lib/cowrie/downloads/{sha256}",
                sha256=sha256,
                timestamp=now,
            ),
        ]
    )
    db_session.flush()

    response = client.get("/api/v1/stats/downloads")
    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    row = body[0]
    assert row["sha256"] == sha256
    assert row["name"] == "meow"
    assert row["sessions"] == 1
    assert row["host"] == "cnc.example.com"
    assert b"var/lib/cowrie/downloads" not in response.data


def test_downloads_name_is_null_when_no_url(client: Any, db_session: Any) -> None:
    now = datetime.now(timezone.utc)
    sha256 = "e" * 64
    db_session.add(
        HoneypotSession(id="dl-002", src_ip="203.0.113.10", src_port=1, started_at=now)
    )
    db_session.flush()
    db_session.add(
        Download(
            session_id="dl-002",
            url=None,
            outfile=f"var/lib/cowrie/downloads/{sha256}",
            sha256=sha256,
            timestamp=now,
        )
    )
    db_session.flush()

    response = client.get("/api/v1/stats/downloads")
    assert response.status_code == 200
    body = response.get_json()
    assert body[0]["name"] is None


def test_download_detail_found(client: Any, db_session: Any) -> None:
    now = datetime.now(timezone.utc)
    sha256 = "d" * 64
    db_session.add(
        HoneypotSession(id="dd-001", src_ip="203.0.113.1", src_port=1, started_at=now)
    )
    db_session.flush()
    db_session.add(
        HoneypotSession(id="dd-002", src_ip="203.0.113.2", src_port=1, started_at=now)
    )
    db_session.flush()
    db_session.add(
        HoneypotSession(id="dd-003", src_ip="203.0.113.3", src_port=1, started_at=now)
    )
    db_session.flush()

    db_session.add(GeoLocation(ip="203.0.113.1", country_code="CN", country="China"))
    db_session.flush()
    db_session.add(GeoLocation(ip="203.0.113.2", country_code="RU", country="Russia"))
    db_session.flush()
    db_session.add(GeoLocation(ip="203.0.113.3", country_code="CN", country="China"))
    db_session.flush()

    db_session.add(
        Download(
            session_id="dd-001",
            url="http://attacker.example.com/payload",
            outfile=f"var/lib/cowrie/downloads/{sha256}",
            sha256=sha256,
            timestamp=now,
        )
    )
    db_session.flush()
    db_session.add(
        Download(
            session_id="dd-002",
            url="http://attacker.example.com/payload",
            outfile=f"var/lib/cowrie/downloads/{sha256}",
            sha256=sha256,
            timestamp=now + timedelta(hours=1),
        )
    )
    db_session.flush()
    db_session.add(
        Download(
            session_id="dd-003",
            url="http://attacker.example.com/payload",
            outfile=f"var/lib/cowrie/downloads/{sha256}",
            sha256=sha256,
            timestamp=now + timedelta(hours=2),
        )
    )
    db_session.flush()

    response = client.get(f"/api/v1/stats/downloads/{sha256}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["sha256"] == sha256
    assert data["name"] == "payload"
    assert data["sessions"] == 3
    assert data["first_seen"] == now.isoformat()
    assert data["last_seen"] == (now + timedelta(hours=2)).isoformat()
    assert len(data["countries"]) == 2
    assert data["countries"][0]["country_code"] == "CN"
    assert data["countries"][0]["sessions"] == 2
    assert data["countries"][1]["country_code"] == "RU"
    assert data["countries"][1]["sessions"] == 1


def test_download_detail_not_found(client: Any) -> None:
    response = client.get(f"/api/v1/stats/downloads/{'a' * 64}")
    assert response.status_code == 404


def test_download_detail_no_raw_ip_leak(client: Any, db_session: Any) -> None:
    """No raw IP addresses in /downloads/<sha256> response."""
    now = datetime.now(timezone.utc)
    sha256 = "c" * 64
    ip = "198.51.100.1"
    db_session.add(HoneypotSession(id="dd-noip", src_ip=ip, src_port=1, started_at=now))
    db_session.flush()
    db_session.add(GeoLocation(ip=ip, country_code="US", country="United States"))
    db_session.flush()
    db_session.add(
        Download(
            session_id="dd-noip",
            url="http://example.com/file",
            outfile=f"var/lib/cowrie/downloads/{sha256}",
            sha256=sha256,
            timestamp=now,
        )
    )
    db_session.flush()

    response = client.get(f"/api/v1/stats/downloads/{sha256}")
    assert response.status_code == 200
    assert ip.encode() not in response.data


def _tcpip_session(db_session: Any, sid: str, ip: str) -> None:
    db_session.add(
        HoneypotSession(
            id=sid, src_ip=ip, src_port=1, started_at=datetime.now(timezone.utc)
        )
    )


def test_downloads_host_is_null_when_url_host_is_an_ip(
    client: Any, db_session: Any
) -> None:
    """Payloads from bare IPs must not borrow session AS org (which names the
    attacker)."""
    now = datetime.now(timezone.utc)
    sha256 = "d" * 64
    _tcpip_session(db_session, "dl-ip", "203.0.113.77")
    db_session.add(
        GeoLocation(ip="203.0.113.77", country_code="US", as_org="Attacker Net LLC")
    )
    db_session.flush()
    db_session.add(
        Download(
            session_id="dl-ip",
            url="http://203.0.113.200/meow",
            outfile=f"var/lib/cowrie/downloads/{sha256}",
            sha256=sha256,
            timestamp=now,
        )
    )
    db_session.flush()

    response = client.get("/api/v1/stats/downloads")
    assert response.status_code == 200
    row = next(r for r in response.get_json() if r["sha256"] == sha256)
    assert row["host"] is None
    assert b"Attacker Net LLC" not in response.data
    assert b"203.0.113.200" not in response.data


def test_tcpip_destinations_group_by_network_not_host(
    client: Any, db_session: Any
) -> None:
    """Multiple IPs on one AS collapse into one row to avoid unshowable IP rows."""
    now = datetime.now(timezone.utc)
    for n, ip in enumerate(("198.51.100.1", "198.51.100.2", "198.51.100.3")):
        _tcpip_session(db_session, f"tc-{n}", f"203.0.113.{100 + n}")
        db_session.flush()
        db_session.add(
            GeoLocation(
                ip=ip, country_code="US", country="United States", as_org="Bigcorp Inc."
            )
        )
        db_session.flush()
        db_session.add(
            DirectTcpipRequest(
                session_id=f"tc-{n}", dst_ip=ip, dst_port=25, timestamp=now
            )
        )
        db_session.flush()

    response = client.get("/api/v1/stats/tcpip-destinations")
    assert response.status_code == 200
    rows = [r for r in response.get_json() if r["network"] == "Bigcorp Inc."]
    assert len(rows) == 1
    assert rows[0] == {
        "network": "Bigcorp Inc.",
        "port": 25,
        "sessions": 3,
        "hosts": 3,
        "country_code": "US",
        "country": "United States",
    }


def test_tcpip_destinations_never_leak_an_ip_shaped_destination(
    client: Any, db_session: Any
) -> None:
    """Invalid-inet destinations (malformed IP-shaped strings) must not leak as row
    labels."""
    now = datetime.now(timezone.utc)
    for n, dst in enumerate(("1.2.3.4.5", "2001:db8:::1", "relay.example.com")):
        _tcpip_session(db_session, f"tl-{n}", f"203.0.113.{200 + n}")
        db_session.flush()
        db_session.add(
            DirectTcpipRequest(
                session_id=f"tl-{n}", dst_ip=dst, dst_port=80, timestamp=now
            )
        )
    db_session.flush()

    response = client.get("/api/v1/stats/tcpip-destinations")
    assert response.status_code == 200
    assert b"1.2.3.4.5" not in response.data
    assert b"2001:db8" not in response.data
    networks = {r["network"] for r in response.get_json()}
    assert "relay.example.com" in networks
    assert None in networks


def test_tcpip_destinations_survive_junk_destination(
    client: Any, db_session: Any
) -> None:
    """Junk dst_ip values must not crash the query; attacker-supplied input can be
    malformed."""
    now = datetime.now(timezone.utc)
    _tcpip_session(db_session, "tj-0", "203.0.113.250")
    db_session.flush()
    db_session.add(
        DirectTcpipRequest(session_id="tj-0", dst_ip="...", dst_port=80, timestamp=now)
    )
    db_session.flush()

    assert client.get("/api/v1/stats/tcpip-destinations").status_code == 200
