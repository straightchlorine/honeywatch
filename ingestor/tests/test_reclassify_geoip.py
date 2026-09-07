"""Tests for the `src.reclassify_geoip` maintenance CLI.

Covers the two load-bearing behaviors: the union-of-known-IPs query (so a
plain rerun reclassifies everything, including IPs that never got a
geo_locations row at all) and the upsert path (including ON CONFLICT
overwriting a stale row).
"""

from __future__ import annotations

import psycopg
import pytest

from src import reclassify_geoip
from src.geoip import GeoData

DbConn = psycopg.Connection[tuple[object, ...]]


def _insert_geo(conn: DbConn, ip: str, *, country_code: str = "US") -> None:
    # ON CONFLICT DO UPDATE for idempotence; _TRUNCATE doesn't clear geo_locations.
    conn.execute(
        """
        INSERT INTO geo_locations (ip, country_code, country, as_org)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ip) DO UPDATE SET
            country_code = EXCLUDED.country_code,
            country = EXCLUDED.country,
            as_org = EXCLUDED.as_org
        """,
        (ip, country_code, "United States", "Old ISP"),
    )


def _insert_session(conn: DbConn, session_id: str, src_ip: str) -> None:
    conn.execute(
        "INSERT INTO sessions (id, src_ip, src_port, dst_port, protocol) "
        "VALUES (%s, %s, %s, %s, %s)",
        (session_id, src_ip, 12345, 22, "ssh"),
    )


def _insert_direct_tcpip(
    conn: DbConn, session_id: str, dst_ip: str, dst_port: int = 443
) -> None:
    conn.execute(
        "INSERT INTO sessions (id, src_ip, src_port, dst_port, protocol) "
        "VALUES (%s, %s, %s, %s, %s)",
        (session_id, "192.168.1.1", 12345, 22, "ssh"),
    )
    conn.execute(
        "INSERT INTO direct_tcpip_requests "
        "(session_id, dst_ip, dst_port, src_ip, src_port, timestamp) "
        "VALUES (%s, %s, %s, %s, %s, now())",
        (session_id, dst_ip, dst_port, "192.168.1.100", 54321),
    )


def test_target_ips_is_union_of_geo_and_sessions(db_connection: DbConn) -> None:
    """Union of geo_locations and sessions IPs, deduped."""
    _insert_geo(db_connection, "1.1.1.1")
    _insert_session(db_connection, "sess-only", "2.2.2.2")
    _insert_geo(db_connection, "3.3.3.3")
    _insert_session(db_connection, "sess-both", "3.3.3.3")

    ips = set(reclassify_geoip._target_ips(db_connection, None))

    assert {"1.1.1.1", "2.2.2.2", "3.3.3.3"} <= ips


def test_target_ips_includes_direct_tcpip_destinations(db_connection: DbConn) -> None:
    """IP literal destinations included; hostnames excluded."""
    _insert_geo(db_connection, "1.1.1.1")
    _insert_session(db_connection, "sess-src", "2.2.2.2")
    _insert_direct_tcpip(db_connection, "sess-tcpip-1", "4.4.4.4")
    _insert_direct_tcpip(db_connection, "sess-tcpip-2", "smtp.example.net")

    ips = set(reclassify_geoip._target_ips(db_connection, None))

    assert {"1.1.1.1", "2.2.2.2", "4.4.4.4"} <= ips
    assert "smtp.example.net" not in ips


def test_target_ips_with_explicit_ip_ignores_db(db_connection: DbConn) -> None:
    """`--ip` targets exactly that address, regardless of what's in the DB."""
    _insert_geo(db_connection, "9.9.9.9")

    assert reclassify_geoip._target_ips(db_connection, "8.8.8.8") == ["8.8.8.8"]


def test_reclassify_upserts_and_overwrites_existing_row(
    db_url: str, db_connection: DbConn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh lookup overwrites a stale geo_locations row (ON CONFLICT path)."""
    ip = "5.5.5.5"
    _insert_geo(db_connection, ip, country_code="US")
    db_connection.commit()  # visible to reclassify()'s own connection

    fresh = GeoData(
        country_code="DE",
        country="Germany",
        city="Berlin",
        latitude=52.5,
        longitude=13.4,
        asn=64500,
        as_org="New ISP",
    )
    monkeypatch.setattr(reclassify_geoip, "geoip_lookup", lambda _ip: fresh)

    reclassify_geoip.reclassify(db_url, ip)

    row = db_connection.execute(
        "SELECT country_code, country, city, asn, as_org FROM geo_locations "
        "WHERE ip = %s",
        (ip,),
    ).fetchone()
    assert row == ("DE", "Germany", "Berlin", 64500, "New ISP")


def test_reclassify_skips_unenrichable_ip(
    db_url: str, db_connection: DbConn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A None lookup result is not upserted - no row is created."""
    ip = "6.6.6.6"
    monkeypatch.setattr(reclassify_geoip, "geoip_lookup", lambda _ip: None)

    reclassify_geoip.reclassify(db_url, ip)

    row = db_connection.execute(
        "SELECT 1 FROM geo_locations WHERE ip = %s", (ip,)
    ).fetchone()
    assert row is None
