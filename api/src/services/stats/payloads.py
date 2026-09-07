"""Payload specimens and egress destinations (Payloads page)."""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import urlparse

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import Session as DbSession

from src.models.direct_tcpip import DirectTcpipRequest
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.redact import redact_ips, safe_host
from src.services.stats.common import DEFAULT_TOP_N
from src.services.types import (
    PayloadCountryRowDict,
    PayloadDetailDict,
    PayloadDownloadDict,
    TcpipDestinationDict,
)


def downloads(db: DbSession, top_n: int = DEFAULT_TOP_N) -> list[PayloadDownloadDict]:
    """Top-N downloaded payloads by session count; machines is a count (never
    addresses), host is None if URL absent (never borrowed)."""
    # Group by sha256, excluding NULL sha256. The join to sessions is what
    # `machines` needs; it is an inner join on the FK, so it cannot change the
    # session count. `machines` is a COUNT of distinct source IPs, never an
    # address - the no-source-IP invariant is not at risk here.
    # Inner join on FK preserves session count; machines is COUNT(DISTINCT
    # src_ip), not addresses.
    sha_group = (
        select(
            Download.sha256,
            func.min(Download.timestamp).label("first_seen"),
            func.max(Download.timestamp).label("last_seen"),
            func.mode().within_group(Download.url).label("most_common_url"),
            func.count(func.distinct(Download.session_id)).label("sessions"),
            func.count(func.distinct(Session.src_ip)).label("machines"),
        )
        .select_from(Download)
        .join(Session, Session.id == Download.session_id)
        .where(Download.sha256.isnot(None))
        .group_by(Download.sha256)
        .order_by(func.count(func.distinct(Download.session_id)).desc())
        .limit(top_n)
        .subquery()
    )

    country_group = (
        select(
            Download.sha256,
            GeoLocation.country_code,
            func.count(func.distinct(Download.session_id)).label("cnt"),
        )
        .select_from(Download)
        .join(Session, Session.id == Download.session_id)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .where(Download.sha256.isnot(None))
        .where(GeoLocation.country_code.isnot(None))
        .group_by(Download.sha256, GeoLocation.country_code)
        .order_by(
            Download.sha256, func.count(func.distinct(Download.session_id)).desc()
        )
        .subquery()
    )

    rows = db.execute(select(sha_group).order_by(sha_group.c.sessions.desc())).all()

    result: list[PayloadDownloadDict] = []
    for row in rows:
        sha256 = row.sha256
        name = _name_from_url(row.most_common_url)
        sessions = row.sessions
        machines = row.machines
        first_seen = row.first_seen.isoformat() if row.first_seen else None
        last_seen = row.last_seen.isoformat() if row.last_seen else None

        countries_for_sha = (
            db.execute(
                select(country_group.c.country_code)
                .where(country_group.c.sha256 == sha256)
                .order_by(country_group.c.cnt.desc())
                .limit(3)
            )
            .scalars()
            .all()
        )

        host = _host_from_url(row.most_common_url)

        result.append(
            {
                "sha256": sha256,
                "name": name,
                "sessions": sessions,
                "machines": machines,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "countries": list(countries_for_sha),
                "host": host,
            }
        )

    return result


def _name_from_url(url: str | None) -> str | None:
    """Extract filename from download URL (attacker's choice, not honeypot's local
    path); None if URL absent or has no basename."""
    if not url:
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    # The basename is taken from the very URL _dump_download redacts, so it
    # gets the same treatment; numeric_hosts=False since a filename like
    # "20240101.bin" is not a host.
    name = redact_ips(PurePosixPath(parsed.path).name, numeric_hosts=False)
    return name or None


def _host_from_url(url: str | None) -> str | None:
    """Hostname from download URL; None if URL absent, unparseable, or host is an IP."""
    if not url:
        return None

    try:
        hostname = urlparse(url).hostname or ""
    except ValueError:
        return None

    return safe_host(hostname)


def tcpip_destinations(db: DbSession, top_n: int = 12) -> list[TcpipDestinationDict]:
    """Top-N direct-tcpip relay targets grouped by destination network (AS org or
    DNS name) and port, since IPs are redacted; network is None if neither
    available."""
    is_ip = "pg_input_is_valid(direct_tcpip_requests.dst_ip, 'inet')"
    is_dns_name = (
        "direct_tcpip_requests.dst_ip ~ '[a-zA-Z]' "
        "AND direct_tcpip_requests.dst_ip !~ ':'"
    )
    network = literal_column(
        f"COALESCE(geo_locations.as_org, CASE WHEN NOT {is_ip} AND {is_dns_name} "
        "THEN direct_tcpip_requests.dst_ip END)"
    ).label("network")

    rows = db.execute(
        select(
            network,
            DirectTcpipRequest.dst_port,
            func.count(func.distinct(DirectTcpipRequest.session_id)).label("sessions"),
            func.count(func.distinct(DirectTcpipRequest.dst_ip)).label("hosts"),
            func.mode().within_group(GeoLocation.country_code).label("country_code"),
            func.mode().within_group(GeoLocation.country).label("country"),
        )
        .select_from(DirectTcpipRequest)
        .outerjoin(
            GeoLocation,
            text(
                f"geo_locations.ip = CASE WHEN {is_ip} "
                "THEN CAST(direct_tcpip_requests.dst_ip AS inet) ELSE NULL END"
            ),
        )
        .group_by(network, DirectTcpipRequest.dst_port)
        .order_by(func.count(func.distinct(DirectTcpipRequest.session_id)).desc())
        .limit(top_n)
    ).all()

    return [
        {
            "network": safe_host(row.network),
            "port": row.dst_port,
            "sessions": row.sessions,
            "hosts": row.hosts,
            "country_code": row.country_code,
            "country": row.country,
        }
        for row in rows
    ]


def payload_detail(db: DbSession, sha256: str) -> PayloadDetailDict | None:
    """Full detail for one downloaded payload (basic info + countries breakdown),
    or None if sha256 has no downloads."""
    sha_row = db.execute(
        select(
            func.min(Download.timestamp).label("first_seen"),
            func.max(Download.timestamp).label("last_seen"),
            func.mode().within_group(Download.url).label("most_common_url"),
            func.count(func.distinct(Download.session_id)).label("sessions"),
        )
        .where(Download.sha256 == sha256)
        .group_by(Download.sha256)
    ).one_or_none()

    if sha_row is None:
        return None

    name = _name_from_url(sha_row.most_common_url)
    first_seen = sha_row.first_seen.isoformat() if sha_row.first_seen else None
    last_seen = sha_row.last_seen.isoformat() if sha_row.last_seen else None

    country_rows = db.execute(
        select(
            GeoLocation.country_code,
            GeoLocation.country,
            func.count(func.distinct(Download.session_id)).label("sessions"),
        )
        .select_from(Download)
        .join(Session, Session.id == Download.session_id)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .where(Download.sha256 == sha256)
        .group_by(GeoLocation.country_code, GeoLocation.country)
        .order_by(func.count(func.distinct(Download.session_id)).desc())
    ).all()

    countries: list[PayloadCountryRowDict] = [
        {
            "country_code": r.country_code,
            "country": r.country,
            "sessions": r.sessions,
        }
        for r in country_rows
    ]

    return {
        "sha256": sha256,
        "name": name,
        "sessions": sha_row.sessions,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "countries": countries,
    }
