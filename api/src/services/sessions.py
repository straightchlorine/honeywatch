from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.serializers import SessionSerializer
from src.services.stats import StatsService
from src.services.types import (
    ActivityBucketDict,
    HeatmapPointDict,
    SessionDetailDict,
    SessionsPageDict,
    TopCountryDict,
    TopPasswordDict,
    TotalsDict,
    TrendDict,
)


def get_sessions_paginated(db: DbSession, page: int, per_page: int) -> SessionsPageDict:
    """Return a page of sessions ordered by most recent first.

    Args:
        db: Active SQLAlchemy session.
        page: 1-indexed page number.
        per_page: Page size; the caller is responsible for clamping.

    Returns:
        A :class:`SessionsPageDict` with the session summaries plus
        pagination metadata.
    """
    offset = (page - 1) * per_page

    total = db.execute(select(func.count()).select_from(Session)).scalar_one()

    stmt = (
        select(Session, GeoLocation)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .options(selectinload(Session.auth_attempts))
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = list(db.execute(stmt).all())

    return {
        "sessions": [SessionSerializer.summary(s, g) for s, g in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


def get_session_detail(db: DbSession, session_id: str) -> SessionDetailDict | None:
    """Return the full detail for a single session, or ``None`` if missing.

    Args:
        db: Active SQLAlchemy session.
        session_id: Cowrie session identifier.

    Returns:
        A :class:`SessionDetailDict` with auth attempts, commands, downloads
        and joined geolocation, or ``None`` when no session matches.
    """
    stmt = (
        select(Session, GeoLocation)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .options(
            selectinload(Session.auth_attempts),
            selectinload(Session.commands),
            selectinload(Session.downloads),
        )
        .where(Session.id == session_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    session, geo = row
    return SessionSerializer.detail(session, geo)


def get_totals(db: DbSession) -> TotalsDict:
    """Return total session, auth-attempt and unique-IP counts."""
    return StatsService(db).totals()


def get_top_passwords(db: DbSession, top_n: int = 10) -> list[TopPasswordDict]:
    """Return the top-N attempted passwords by count, descending."""
    return StatsService(db, top_n=top_n).top_passwords()


def get_top_countries(db: DbSession, top_n: int = 10) -> list[TopCountryDict]:
    """Return the top-N attacking countries by session count, descending."""
    return StatsService(db, top_n=top_n).top_countries()


def get_activity(db: DbSession, bucket: str) -> list[ActivityBucketDict]:
    """Return session counts grouped by the given time bucket.

    Raises:
        ValueError: For unsupported ``bucket`` values.
    """
    return StatsService(db).activity(bucket)


def get_trend(db: DbSession, period_days: int = 7) -> TrendDict:
    """Return the session-count trend over the last ``period_days``."""
    return StatsService(db).trend(period_days)


def get_heatmap(db: DbSession) -> list[HeatmapPointDict]:
    """Return session counts per (weekday, hour) cell."""
    return StatsService(db).heatmap()
