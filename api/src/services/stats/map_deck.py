"""Map deck data: choropleth countries + city markers (Overview page)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Numeric, cast, func, select
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.types import MapCityDict, MapCountryDict, MapDataDict

# Per-country cap on the Overview map's city markers, applied via a window
# function (not a flat global LIMIT) to prevent small countries being
# crowded out by a few countries with huge single cities.
MAP_CITY_TOP_N_PER_COUNTRY = 5

# Low-signal cutoff for city markers; a city with a handful of sessions is
# noise at map scale. Does not apply to the country-detail drawer's top_cities
# (a scrollable list, not a spatial marker layer).
MAP_CITY_MIN_SESSIONS = 50


def _sessions_per_ip():
    """Subquery collapsing sessions to one (src_ip, count) row per source IP."""
    return (
        select(Session.src_ip, func.count().label("cnt"))
        .group_by(Session.src_ip)
        .subquery()
    )


def map_countries(db: DbSession) -> list[MapCountryDict]:
    """Every resolved country with a choropleth-ready metric row.

    Unresolved sessions (`country_code IS NULL`) are excluded - the map has
    nowhere to draw them; the Unknown bucket lives on the Origins ranked list
    instead.
    """
    per_ip = _sessions_per_ip()
    cc = GeoLocation.country_code
    sess_agg = (
        select(
            cc.label("a2"),
            cast(func.sum(per_ip.c.cnt), BigInteger).label("sessions"),
            func.count().label("ips"),
        )
        .select_from(per_ip)
        .join(GeoLocation, GeoLocation.ip == per_ip.c.src_ip)
        .where(cc.isnot(None))
        .group_by(cc)
        .subquery()
    )
    auth_agg = (
        select(
            GeoLocation.country_code.label("a2"),
            func.count().label("attempts"),
            func.count().filter(AuthAttempt.success.is_(True)).label("successful"),
        )
        .select_from(AuthAttempt)
        .join(Session, Session.id == AuthAttempt.session_id)
        .join(GeoLocation, GeoLocation.ip == Session.src_ip)
        .where(GeoLocation.country_code.isnot(None))
        .group_by(GeoLocation.country_code)
        .subquery()
    )
    rows = db.execute(
        select(
            sess_agg.c.a2,
            sess_agg.c.sessions,
            sess_agg.c.ips,
            auth_agg.c.attempts,
            auth_agg.c.successful,
        )
        .select_from(sess_agg)
        .outerjoin(auth_agg, auth_agg.c.a2 == sess_agg.c.a2)
        .order_by(sess_agg.c.sessions.desc())
    ).all()
    out: list[MapCountryDict] = []
    for r in rows:
        attempts = r.attempts or 0
        successful = r.successful or 0
        out.append(
            {
                "a2": r.a2,
                "sessions": r.sessions,
                "ips": r.ips,
                "success_rate": (
                    round(successful / attempts * 100, 2) if attempts else None
                ),
            }
        )
    return out


def map_cities(
    db: DbSession,
    country: str | None = None,
    top_n: int | None = None,
    min_sessions: int | None = None,
) -> list[MapCityDict]:
    """City markers by session count, merging jittered coordinates.

    Two merge passes: first by (round(lat, 1), round(lon, 1)) so nearby
    jittered points collapse into one marker per pass ("mode()" picks the
    most common city name within that bucket for a deterministic label);
    then a SECOND pass merges any of those buckets that share the same
    (city, country_code) - MaxMind sometimes resolves different IP ranges
    within the same city (different ISPs/ASNs) to representative coordinates
    more than 0.05 degrees apart, which the first pass alone doesn't catch,
    producing duplicate-looking rows like two separate "Jakarta" entries a
    few km apart. The merged row's session count is the sum across every
    sub-cluster sharing that city name; its lat/lon is the sub-cluster with
    the most sessions (the most-trafficked/likely-authoritative point for
    that city), not an average (which could land the marker somewhere
    between two ISP-specific approximations, less accurate than either).
    """
    per_ip = _sessions_per_ip()
    lat_r = func.round(cast(GeoLocation.latitude, Numeric), 1).label("lat")
    lon_r = func.round(cast(GeoLocation.longitude, Numeric), 1).label("lon")
    city_mode = func.mode().within_group(GeoLocation.city).label("city")
    country_mode = (
        func.mode().within_group(GeoLocation.country_code).label("country_code")
    )
    sessions = cast(func.sum(per_ip.c.cnt), BigInteger).label("sessions")
    base = (
        select(city_mode, country_mode, lat_r, lon_r, sessions)
        .select_from(per_ip)
        .join(GeoLocation, GeoLocation.ip == per_ip.c.src_ip)
        .where(GeoLocation.city.isnot(None))
        .where(GeoLocation.country_code.isnot(None))
        .where(GeoLocation.latitude.isnot(None))
        .where(GeoLocation.longitude.isnot(None))
    )
    if country is not None:
        base = base.where(GeoLocation.country_code == country)
    base = base.group_by(lat_r, lon_r)
    subclusters = base.subquery()

    merged_sessions = (
        func.sum(subclusters.c.sessions)
        .over(partition_by=(subclusters.c.city, subclusters.c.country_code))
        .label("sessions")
    )
    pick_rn = (
        func.row_number()
        .over(
            partition_by=(subclusters.c.city, subclusters.c.country_code),
            order_by=subclusters.c.sessions.desc(),
        )
        .label("pick_rn")
    )
    merged = select(
        subclusters.c.city,
        subclusters.c.country_code,
        subclusters.c.lat,
        subclusters.c.lon,
        merged_sessions,
        pick_rn,
    ).subquery()
    grouped = (
        select(
            merged.c.city,
            merged.c.country_code,
            merged.c.lat,
            merged.c.lon,
            merged.c.sessions,
        )
        .where(merged.c.pick_rn == 1)
        .subquery()
    )

    if country is None and top_n is not None:
        # Whole-map case: rank each city within its own country so small
        # countries aren't crowded out of a flat global top-N.
        rn = (
            func.row_number()
            .over(
                partition_by=grouped.c.country_code,
                order_by=grouped.c.sessions.desc(),
            )
            .label("rn")
        )
        ranked = select(grouped, rn).subquery()
        stmt = (
            select(ranked)
            .where(ranked.c.rn <= top_n)
            .order_by(ranked.c.sessions.desc())
        )
        if min_sessions is not None:
            stmt = stmt.where(ranked.c.sessions >= min_sessions)
    else:
        stmt = select(grouped).order_by(grouped.c.sessions.desc())
        if min_sessions is not None:
            stmt = stmt.where(grouped.c.sessions >= min_sessions)
        if top_n is not None:
            stmt = stmt.limit(top_n)

    rows = db.execute(stmt).all()
    return [
        {
            "city": r.city,
            "country_code": r.country_code,
            "lat": float(r.lat),
            "lon": float(r.lon),
            "sessions": r.sessions,
        }
        for r in rows
    ]


def map_data(db: DbSession) -> MapDataDict:
    """One payload for the Overview map deck: choropleth + city markers."""
    return {
        "countries": map_countries(db),
        "cities": map_cities(
            db, top_n=MAP_CITY_TOP_N_PER_COUNTRY, min_sessions=MAP_CITY_MIN_SESSIONS
        ),
    }
