from __future__ import annotations

from typing import Any

from sqlalchemy import and_, asc, exists, func, nulls_last, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.serializers import SessionSerializer
from src.services.types import SessionDetailDict, SessionsPageDict


def get_sessions_paginated(
    db: DbSession,
    page: int,
    per_page: int,
    *,
    country: str | None = None,
    category: str | None = None,
    sort: str = "recent",
) -> SessionsPageDict:
    """Return a filtered, sorted page of session summaries.

    Filters and ordering are applied in SQL so pagination metadata stays
    consistent with the rendered page.

    Args:
        db: Active SQLAlchemy session.
        page: 1-indexed page number.
        per_page: Page size; the caller is responsible for clamping.
        country: ISO 3166-1 alpha-2 code to filter the source country, or None.
        category: Mutually exclusive session class to keep -- ``"active"`` (ran
            commands), ``"login"`` (login accepted, no commands), ``"failed"``
            (attempts made, none accepted), ``"probe"`` (no login attempts), or
            None for no class filter. Mirrors the dashboard's classification.
        sort: ``"recent"`` (newest first), ``"country"`` (source country A-Z),
            or ``"active"`` (most commands first).

    Returns:
        A :class:`SessionsPageDict` with the session summaries plus pagination
        metadata.
    """
    offset = (page - 1) * per_page

    success_exists = exists().where(
        and_(AuthAttempt.session_id == Session.id, AuthAttempt.success.is_(True))
    )
    auth_exists = exists().where(AuthAttempt.session_id == Session.id)
    commands_exists = exists().where(Command.session_id == Session.id)
    # Per-row counters aggregated in SQL so we never materialize the commands /
    # auth_attempts collections just to count them (a brute-force session can
    # hold thousands of auth rows). Selected as columns and passed to the
    # serializer; the list query carries no `selectinload`.
    command_count = (
        select(func.count())
        .select_from(Command)
        .where(Command.session_id == Session.id)
        .correlate(Session)
        .scalar_subquery()
    )
    auth_attempt_count = (
        select(func.count())
        .select_from(AuthAttempt)
        .where(AuthAttempt.session_id == Session.id)
        .correlate(Session)
        .scalar_subquery()
    )
    login_success = (
        select(func.coalesce(func.bool_or(AuthAttempt.success), False))
        .select_from(AuthAttempt)
        .where(AuthAttempt.session_id == Session.id)
        .correlate(Session)
        .scalar_subquery()
    )

    conditions: list[Any] = []
    if country:
        conditions.append(GeoLocation.country_code == country)
    # Classification filter -- the same partition the dashboard badges use, so
    # exactly one class matches any session (commands > login > failed > probe).
    if category == "active":
        conditions.append(commands_exists)
    elif category == "login":
        conditions.append(and_(~commands_exists, success_exists))
    elif category == "failed":
        conditions.append(and_(~commands_exists, ~success_exists, auth_exists))
    elif category == "probe":
        conditions.append(and_(~commands_exists, ~auth_exists))

    count_stmt = (
        select(func.count(Session.id))
        .select_from(Session)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
    )
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = db.execute(count_stmt).scalar_one()

    if sort == "country":
        order_by: list[Any] = [
            nulls_last(asc(GeoLocation.country)),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    elif sort == "active":
        order_by = [command_count.desc(), Session.started_at.desc(), Session.id.desc()]
    else:  # recent
        order_by = [Session.started_at.desc(), Session.id.desc()]

    stmt = select(
        Session,
        GeoLocation,
        command_count.label("command_count"),
        auth_attempt_count.label("auth_attempt_count"),
        login_success.label("login_success"),
    ).outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
    for cond in conditions:
        stmt = stmt.where(cond)
    stmt = stmt.order_by(*order_by).offset(offset).limit(per_page)
    rows = db.execute(stmt).all()

    return {
        "sessions": [
            SessionSerializer.summary(
                s,
                g,
                command_count=cc,
                auth_attempt_count=ac,
                login_success=ls,
            )
            for s, g, cc, ac, ls in rows
        ],
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
