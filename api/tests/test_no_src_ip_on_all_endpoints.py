"""Blanket privacy gate: no API response body contains the literal `src_ip`.

Substring check covers JSON keys, examples, error envelopes. Runs against
seeded data so every endpoint produces a non-empty response.
"""

from __future__ import annotations

from typing import Any

ENDPOINTS = [
    "/api/v1/sessions/",
    "/api/v1/sessions/sess-001",
    "/api/v1/stats/totals",
    "/api/v1/stats/top-passwords",
    "/api/v1/stats/top-countries",
    "/api/v1/stats/top-credentials",
    "/api/v1/stats/auth-outcomes",
    "/api/v1/stats/password-composition",
    "/api/v1/stats/passwords-by-length?length=5",
    "/api/v1/stats/activity",
    "/api/v1/stats/trend",
    "/api/v1/stats/heatmap",
]


def test_no_src_ip_in_any_response(client: Any, seed_data: dict[str, Any]) -> None:
    del seed_data
    for url in ENDPOINTS:
        response = client.get(url)
        assert response.status_code == 200, f"{url} returned {response.status_code}"
        assert b"src_ip" not in response.data, f"{url} leaked src_ip"
