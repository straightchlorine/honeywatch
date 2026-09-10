"""Per-country and per-network attack breakdowns (Countries page)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ColumnElement, cast, func, nulls_last, select, true
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.stats.activity import activity
from src.services.stats.common import (
    DEFAULT_TOP_N,
    UNKNOWN_COUNTRY,
    country_match,
    require_one_of,
)
from src.services.stats.credentials import top_credentials
from src.services.stats.map_deck import map_cities
from src.services.types import (
    CountriesDict,
    CountryAsnDict,
    CountryDetailDict,
    CountryRowDict,
    TopCountryDict,
)

# Drawer bundle sub-lists stay short - it is a summary panel, not a leaderboard page.
DRAWER_TOP_N = 5

VALID_COUNTRY_SORTS = frozenset({"sessions", "ips", "attempts", "success_rate"})

UNKNOWN_COUNTRY_NAME = "Unknown"


def _sessions_per_ip():
    """Sessions aggregated per source IP."""
    return (
        select(Session.src_ip, func.count().label("cnt"))
        .group_by(Session.src_ip)
        .subquery()
    )


def _direction(col: ColumnElement[Any], resolved_order: str) -> ColumnElement[Any]:
    """asc()/desc() for one column; every sort key routes through this so the
    four order_by branches cannot drift apart."""
    return col.asc() if resolved_order == "asc" else col.desc()


def top_countries(db: DbSession, top_n: int = DEFAULT_TOP_N) -> list[TopCountryDict]:
    """Top-N countries by session count; unresolved IPs use UNKNOWN_COUNTRY."""
    per_ip = _sessions_per_ip()
    country_code = func.coalesce(GeoLocation.country_code, UNKNOWN_COUNTRY).label(
        "country_code"
    )
    country = func.coalesce(GeoLocation.country, UNKNOWN_COUNTRY_NAME).label("country")
    count = cast(func.sum(per_ip.c.cnt), BigInteger).label("count")
    rows = db.execute(
        select(country_code, country, count)
        .select_from(per_ip)
        .outerjoin(GeoLocation, GeoLocation.ip == per_ip.c.src_ip)
        .group_by(country_code, country)
        .order_by(count.desc())
        .limit(top_n)
    ).all()
    return [{"country_code": r[0], "country": r[1], "count": r[2]} for r in rows]


def country_breakdown(
    db: DbSession,
    sort: str = "sessions",
    top_n: int = DEFAULT_TOP_N,
    order: str | None = None,
) -> CountriesDict:
    """Top-N countries ranked by sort key; countries with no attempts sort last on
    success_rate. All four sort keys default to descending; order= overrides it."""
    require_one_of(sort, VALID_COUNTRY_SORTS, "sort")

    # Pre-aggregate per src_ip to reduce geo join cardinality.
    per_ip = _sessions_per_ip()
    sess_cc = func.coalesce(GeoLocation.country_code, UNKNOWN_COUNTRY).label(
        "country_code"
    )
    sess_country = func.coalesce(GeoLocation.country, UNKNOWN_COUNTRY_NAME).label(
        "country"
    )
    sess_agg = (
        select(
            sess_cc,
            sess_country,
            cast(func.sum(per_ip.c.cnt), BigInteger).label("sessions"),
            func.count().label("distinct_ips"),
        )
        .select_from(per_ip)
        .outerjoin(GeoLocation, GeoLocation.ip == per_ip.c.src_ip)
        .group_by(sess_cc, sess_country)
        .subquery()
    )

    # One pass grouped by country.
    auth_cc = func.coalesce(GeoLocation.country_code, UNKNOWN_COUNTRY).label(
        "country_code"
    )
    auth_agg = (
        select(
            auth_cc,
            cast(func.count(), BigInteger).label("attempts"),
            cast(func.count().filter(AuthAttempt.success.is_(True)), BigInteger).label(
                "successful"
            ),
        )
        .select_from(AuthAttempt)
        .join(Session, Session.id == AuthAttempt.session_id)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .group_by(auth_cc)
        .subquery()
    )

    sessions = sess_agg.c.sessions
    distinct_ips = sess_agg.c.distinct_ips
    attempts = func.coalesce(auth_agg.c.attempts, 0).label("attempts")
    successful = func.coalesce(auth_agg.c.successful, 0).label("successful")
    # No -1.0 sentinel: nulls_last() keeps no-attempt countries last in BOTH
    # directions. The old sentinel only worked for the DESC default - reversed,
    # it would sort those countries FIRST instead of last.
    rate_order = auth_agg.c.successful * 1.0 / func.nullif(auth_agg.c.attempts, 0)
    resolved_order = order or "desc"  # all four keys default desc
    order_by = {
        "sessions": _direction(sessions, resolved_order),
        "ips": _direction(distinct_ips, resolved_order),
        "attempts": _direction(attempts, resolved_order),
        "success_rate": nulls_last(_direction(rate_order, resolved_order)),
    }[sort]

    rows = db.execute(
        select(
            sess_agg.c.country_code,
            sess_agg.c.country,
            sessions,
            distinct_ips,
            attempts,
            successful,
        )
        .select_from(sess_agg)
        .outerjoin(auth_agg, auth_agg.c.country_code == sess_agg.c.country_code)
        # sessions, then country_code, as stable tiebreakers for equal-rank rows.
        .order_by(order_by, sessions.desc(), sess_agg.c.country_code)
        .limit(top_n)
    ).all()

    countries: list[CountryRowDict] = []
    for r in rows:
        att = r.attempts
        countries.append(
            {
                "country_code": r.country_code,
                "country": r.country,
                "sessions": r.sessions,
                "distinct_ips": r.distinct_ips,
                "attempts": att,
                "successful": r.successful,
                "success_rate": round(r.successful / att * 100, 2) if att else None,
            }
        )

    # Header counters must span all countries, not just the top-N page.
    header_ip = _sessions_per_ip()
    header = db.execute(
        select(
            cast(func.sum(header_ip.c.cnt), BigInteger).label("total"),
            cast(
                func.coalesce(
                    func.sum(header_ip.c.cnt).filter(
                        GeoLocation.country_code.isnot(None)
                    ),
                    0,
                ),
                BigInteger,
            ).label("resolved"),
            func.count(func.distinct(GeoLocation.country_code)).label(
                "total_countries"
            ),
        )
        .select_from(header_ip)
        .outerjoin(GeoLocation, GeoLocation.ip == header_ip.c.src_ip)
    ).one()
    geo_resolved_pct = (
        round(header.resolved / header.total * 100, 2) if header.total else None
    )
    return {
        "countries": countries,
        "total_countries": header.total_countries,
        "geo_resolved_pct": geo_resolved_pct,
    }


def country_asns(
    db: DbSession, country: str | None = None, top_n: int = DEFAULT_TOP_N
) -> list[CountryAsnDict]:
    """Top-N source networks (ASN / org) by session count.

    `country` scopes to one alpha-2 code or UNKNOWN_COUNTRY. No country_code
    is returned for an ASN because GeoLite2 has no notion of ASN's real country,
    and modal geolocation is meaningless when filtered to a single country.
    """
    per_ip = (
        select(func.count().label("cnt"))
        .where(Session.src_ip == GeoLocation.ip)
        .correlate(GeoLocation)
        .lateral("per_ip")
    )
    sessions = cast(func.sum(per_ip.c.cnt), BigInteger).label("sessions")
    distinct_ips = func.count().label("distinct_ips")
    stmt = (
        select(GeoLocation.asn, GeoLocation.as_org, sessions, distinct_ips)
        .select_from(GeoLocation)
        .join(per_ip, true())
        .where(GeoLocation.asn.isnot(None))
        .where(per_ip.c.cnt > 0)
    )
    # GeoLocation is already the driving table; filter directly instead of using
    # scope_to_country.
    if country is not None:
        stmt = stmt.where(country_match(country))
    rows = db.execute(
        stmt.group_by(GeoLocation.asn, GeoLocation.as_org)
        .order_by(sessions.desc())
        .limit(top_n)
    ).all()
    return [
        {
            "asn": r.asn,
            "as_org": r.as_org,
            "sessions": r.sessions,
            "distinct_ips": r.distinct_ips,
        }
        for r in rows
    ]


def country_detail(db: DbSession, a2: str) -> CountryDetailDict | None:
    """Intel-drawer bundle for one country; returns None if no sessions found."""
    per_ip = _sessions_per_ip()
    cc = GeoLocation.country_code
    sess_row = db.execute(
        select(
            func.mode().within_group(GeoLocation.country).label("name"),
            cast(func.sum(per_ip.c.cnt), BigInteger).label("sessions"),
            func.count().label("ips"),
        )
        .select_from(per_ip)
        .join(GeoLocation, GeoLocation.ip == per_ip.c.src_ip)
        .where(cc == a2)
    ).one()
    if sess_row.sessions is None:
        return None

    auth_row = db.execute(
        select(
            func.count().label("attempts"),
            func.count().filter(AuthAttempt.success.is_(True)).label("successful"),
        )
        .select_from(AuthAttempt)
        .join(Session, Session.id == AuthAttempt.session_id)
        .join(GeoLocation, GeoLocation.ip == Session.src_ip)
        .where(GeoLocation.country_code == a2)
    ).one()
    attempts = auth_row.attempts
    successful = auth_row.successful

    # Drawer shows only the last 14 days of the trailing 30-day activity window.
    daily = activity(db, "day", country=a2)[-14:]
    top_cities = map_cities(db, country=a2, top_n=5)

    return {
        "a2": a2,
        "name": sess_row.name or UNKNOWN_COUNTRY_NAME,
        "sessions": sess_row.sessions,
        "ips": sess_row.ips,
        "attempts": attempts,
        "success_rate": round(successful / attempts * 100, 2) if attempts else None,
        "top_asns": country_asns(db, country=a2, top_n=DRAWER_TOP_N),
        "top_credentials": top_credentials(db, country=a2, top_n=DRAWER_TOP_N),
        "daily": [{"date": b["bucket"][:10], "sessions": b["count"]} for b in daily],
        "top_cities": top_cities,
    }
