from datetime import datetime, timedelta, timezone
from typing import Any

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
    """Sessions without a geo row appear under "Unknown" (outer join + COALESCE).

    The ingestor splits session and geo writes so a session row can exist
    before (or without) its geo enrichment. Inner-joining would silently
    undercount the leaderboard; bucketing as Unknown surfaces the gap.
    """
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
    # marshmallow OneOf validation produces a 422 from flask-smorest
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
    """``pct_change`` is ``None`` when the prior window has no sessions."""
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
    # period_days > 365 fails validate.Range, surfacing 422 (strict validation,
    # no silent clamp).
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
    """Default grouping returns username+password pairs ranked by count."""
    del seed_data
    response = client.get("/api/v1/stats/top-credentials")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    # seed has 3 distinct pairs, each tried once.
    assert {(r["username"], r["password"]) for r in data} == {
        ("root", "password123"),
        ("admin", "admin"),
        ("root", "toor"),
    }
    counts = [r["count"] for r in data]
    assert counts == sorted(counts, reverse=True)
    # distinct_ips is null for the (default) attempts metric -- no sessions join.
    assert all(r["distinct_ips"] is None for r in data)


def test_top_credentials_by_username(client: Any, seed_data: Any) -> None:
    """Grouping by username collapses the password (None) and sums attempts."""
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?by=username")
    assert response.status_code == 200
    data = response.get_json()
    assert all(r["password"] is None for r in data)
    by_user = {r["username"]: r["count"] for r in data}
    # root appears in two attempts (password123 + toor); admin once.
    assert by_user == {"root": 2, "admin": 1}
    # ranked descending, so the most-tried username is first.
    assert data[0]["username"] == "root"


def test_top_credentials_by_password(client: Any, seed_data: Any) -> None:
    """Grouping by password alone collapses the username (None)."""
    del seed_data
    response = client.get("/api/v1/stats/top-credentials?by=password")
    assert response.status_code == 200
    data = response.get_json()
    assert all(r["username"] is None for r in data)
    # seed passwords: password123, admin, toor -- each tried once.
    assert {r["password"] for r in data} == {"password123", "admin", "toor"}


def test_top_credentials_success_only(client: Any, seed_data: Any) -> None:
    """outcome=success returns only the cowrie-accepted credential(s)."""
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
    # every seeded pair was tried from exactly one source IP.
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


def test_password_composition(client: Any, seed_data: Any) -> None:
    del seed_data
    response = client.get("/api/v1/stats/password-composition")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 3
    assert data["capped_at"] == 16
    # lengths: password123=11, admin=5, toor=4 -> three single-count buckets.
    lengths = {row["length"]: row["count"] for row in data["lengths"]}
    assert lengths == {4: 1, 5: 1, 11: 1}
    # charset classes: admin + toor are lowercase, password123 is alnum.
    classes = {row["name"]: row["count"] for row in data["classes"]}
    assert classes == {"lower": 2, "alnum": 1}
    # descending by count, so the dominant class leads.
    assert data["classes"][0]["name"] == "lower"


def test_password_composition_charset_classes_cover_every_branch(
    client: Any, charset_seed: Any
) -> None:
    """Every branch of the server-side charset CASE is exercised and prioritized.

    The classifier (stats.py: empty -> symbol -> digits -> lower -> upper ->
    alnum) is order-sensitive: 'p@ss!' contains digits/letters but must land in
    'symbol' because that branch comes first, etc. Lock the whole priority chain.
    """
    del charset_seed
    response = client.get("/api/v1/stats/password-composition")
    assert response.status_code == 200
    classes = {row["name"]: row["count"] for row in response.get_json()["classes"]}
    # 'secret' + the 18-char all-lowercase LONG_PASSWORD both classify as lower.
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
    # seed passwords: password123 (11), admin (5), toor (4).
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

    ``charset_seed`` includes an 18-char password (> the cap of 16). Querying
    ``length=16`` must return it via the ``length_col >= cap`` tail branch, while
    a sub-cap exact query (``length=11``) must NOT -- the 18-char row only
    matches the inclusive tail, not an exact-length lookup.
    """
    del charset_seed
    assert len(LONG_PASSWORD) >= 16
    tail = client.get("/api/v1/stats/passwords-by-length?length=16").get_json()
    assert {row["password"] for row in tail} == {LONG_PASSWORD}
    # the exact-length branch (< cap) does not pick up the longer password.
    exact = client.get("/api/v1/stats/passwords-by-length?length=11").get_json()
    assert all(row["password"] != LONG_PASSWORD for row in exact)


def test_passwords_by_length_requires_length(client: Any) -> None:
    # length is required; omitting it is a 422 (no silent default).
    assert client.get("/api/v1/stats/passwords-by-length").status_code == 422


def test_passwords_by_length_rejects_out_of_range(client: Any) -> None:
    assert client.get("/api/v1/stats/passwords-by-length?length=-1").status_code == 422
    assert client.get("/api/v1/stats/passwords-by-length?length=99").status_code == 422
