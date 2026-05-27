from datetime import datetime, timedelta, timezone
from typing import Any

from src.models.session import Session as HoneypotSession


def test_totals(client: Any, seed_data: Any) -> None:
    response = client.get("/api/stats/totals")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_sessions"] == 2
    assert data["total_auth_attempts"] == 3
    assert data["unique_ips"] == 2


def test_top_passwords(client: Any, seed_data: Any) -> None:
    response = client.get("/api/stats/top-passwords")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    counts = [row["count"] for row in data]
    assert counts == sorted(counts, reverse=True)


def test_top_passwords_top_n_clamp(client: Any, seed_data: Any) -> None:
    response = client.get("/api/stats/top-passwords?top_n=1")
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def test_top_countries_empty_until_enricher(client: Any, seed_data: Any) -> None:
    """``top-countries`` returns ``[]`` until PR-B's geo enricher populates rows."""
    response = client.get("/api/stats/top-countries")
    assert response.status_code == 200
    assert response.get_json() == []


def test_activity_each_bucket(client: Any, seed_data: Any) -> None:
    for bucket in ("hour", "day", "month"):
        response = client.get(f"/api/stats/activity?bucket={bucket}")
        assert response.status_code == 200, bucket
        data = response.get_json()
        assert isinstance(data, list)
        for row in data:
            assert "bucket" in row
            assert "count" in row


def test_activity_invalid_bucket(client: Any) -> None:
    response = client.get("/api/stats/activity?bucket=fortnight")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_activity_default_bucket_is_day(client: Any, seed_data: Any) -> None:
    response = client.get("/api/stats/activity")
    assert response.status_code == 200


def test_trend_default(client: Any, seed_data: Any) -> None:
    response = client.get("/api/stats/trend")
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

    response = client.get("/api/stats/trend?period_days=3")
    assert response.status_code == 200
    data = response.get_json()
    assert data["current"] == 1
    assert data["previous"] == 0
    assert data["delta"] == 1
    assert data["pct_change"] is None


def test_trend_period_days_clamped(client: Any) -> None:
    response = client.get("/api/stats/trend?period_days=99999")
    assert response.status_code == 200


def test_heatmap(client: Any, seed_data: Any) -> None:
    response = client.get("/api/stats/heatmap")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    for row in data:
        assert set(row.keys()) == {"hour", "weekday", "count"}
        assert 0 <= row["hour"] <= 23
        assert 0 <= row["weekday"] <= 6
