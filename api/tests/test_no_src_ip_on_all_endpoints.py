"""Blanket privacy gate: no API response body contains the literal `src_ip`.

Substring check covers JSON keys, examples, error envelopes. Runs against
seeded data so every endpoint produces a non-empty response.
"""

from __future__ import annotations

from typing import Any


def test_no_src_ip_in_any_response(
    client: Any, get_urls: Any, seed_data: dict[str, Any]
) -> None:
    downloads = seed_data.get("downloads", [])
    download_sha256 = downloads[0].sha256 if downloads else "a" * 64

    # ?country= variants aren't path/query args enumeration can infer.
    extras = [
        "/api/v1/stats/top-credentials?country=US",
        "/api/v1/stats/top-credentials?country=??",
        "/api/v1/stats/asns?country=??",
    ]
    urls = get_urls(session_id="sess-001", sha256=download_sha256, a2="US") + extras

    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, f"{url} returned {response.status_code}"
        assert b"src_ip" not in response.data, f"{url} leaked src_ip"
