"""Blanket privacy gate: no API response body contains the literal `src_ip`.

Substring check covers JSON keys, examples, error envelopes. Runs against
seeded data so every endpoint produces a non-empty response.
"""

from __future__ import annotations

from typing import Any


def test_no_src_ip_in_any_response(client: Any, seed_data: dict[str, Any]) -> None:
    downloads = seed_data.get("downloads", [])
    download_sha256 = downloads[0].sha256 if downloads else "a" * 64

    endpoints = [
        "/api/v1/sessions/",
        "/api/v1/sessions/sess-001",
        "/api/v1/stats/totals",
        "/api/v1/stats/top-passwords",
        "/api/v1/stats/top-countries",
        "/api/v1/stats/countries",
        "/api/v1/stats/asns",
        "/api/v1/stats/top-credentials",
        "/api/v1/stats/top-credentials?country=US",
        "/api/v1/stats/top-credentials?country=??",
        "/api/v1/stats/asns?country=??",
        "/api/v1/stats/auth-outcomes",
        "/api/v1/stats/password-composition",
        "/api/v1/stats/passwords-by-length?length=5",
        "/api/v1/stats/activity",
        "/api/v1/stats/trend",
        "/api/v1/stats/heatmap",
        "/api/v1/stats/map",
        "/api/v1/stats/downloads",
        f"/api/v1/stats/downloads/{download_sha256}",
        "/api/v1/stats/tcpip-destinations",
        "/api/v1/stats/ssh-clients",
        "/api/v1/stats/fingerprints",
    ]

    for url in endpoints:
        response = client.get(url)
        assert response.status_code == 200, f"{url} returned {response.status_code}"
        assert b"src_ip" not in response.data, f"{url} leaked src_ip"
