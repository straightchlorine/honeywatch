"""Lower-bound / upper-bound / type 422 paths for every query schema.

Marshmallow validators run at the boundary; these tests ensure a regression
that loosens any bound (e.g. `min=1` -> `min=0`) fails fast in CI.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/sessions/?page=0",
        "/api/v1/sessions/?page=-1",
        "/api/v1/sessions/?page=99999",
        "/api/v1/sessions/?page=abc",
        "/api/v1/sessions/?per_page=0",
        "/api/v1/sessions/?per_page=-1",
        "/api/v1/sessions/?per_page=99999",
        "/api/v1/sessions/?per_page=abc",
    ],
)
def test_sessions_list_invalid_query_returns_422(client: Any, url: str) -> None:
    response = client.get(url)
    assert response.status_code == 422, url


@pytest.mark.parametrize(
    "endpoint",
    ["/api/v1/stats/top-passwords", "/api/v1/stats/top-countries"],
)
@pytest.mark.parametrize("bad", ["0", "-1", "101", "abc"])
def test_stats_top_n_invalid_returns_422(client: Any, endpoint: str, bad: str) -> None:
    response = client.get(f"{endpoint}?top_n={bad}")
    assert response.status_code == 422


@pytest.mark.parametrize("bad", ["year", "minute", "", "1; DROP TABLE"])
def test_stats_activity_invalid_bucket_returns_422(client: Any, bad: str) -> None:
    response = client.get(f"/api/v1/stats/activity?bucket={bad}")
    assert response.status_code == 422


@pytest.mark.parametrize("bad", ["0", "-1", "366", "abc"])
def test_stats_trend_invalid_period_days_returns_422(client: Any, bad: str) -> None:
    response = client.get(f"/api/v1/stats/trend?period_days={bad}")
    assert response.status_code == 422


def test_session_id_too_long_returns_422(client: Any) -> None:
    response = client.get("/api/v1/sessions/" + ("a" * 65))
    assert response.status_code == 422


def test_session_id_charset_returns_422(client: Any) -> None:
    response = client.get("/api/v1/sessions/!!!")
    assert response.status_code == 422


def test_404_envelope_matches_smorest_shape(client: Any) -> None:
    response = client.get("/api/v1/sessions/aaaaaaaa")
    assert response.status_code == 404
    body = response.get_json()
    assert isinstance(body, dict)
    assert body.get("code") == 404
    assert (
        "Session" in body.get("message", "")
        or "not found" in body.get("message", "").lower()
    )
    assert "aaaaaaaa" not in body.get("message", "")  # no user-input echo


def test_unmapped_path_returns_json_404(client: Any) -> None:
    """Old errorhandler(404) removed; replacement must keep JSON shape."""
    response = client.get("/api/v9/does-not-exist")
    assert response.status_code == 404
    assert response.mimetype == "application/json"
    body = response.get_json()
    assert body["code"] == 404
