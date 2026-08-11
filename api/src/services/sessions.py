"""Session queries: paginated lists and per-session detail."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, asc, exists, func, nulls_last, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.serializers import session_detail, session_summary
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
    """One page of session summaries, filtered and sorted in SQL.

    Arguments:
      db: DbSession — database connection
      page: int — 1-indexed page number; clamping happens in schema, not here
      per_page: int — items per page; clamping happens in schema
      country: str | None — filter by country code
      category: str | None — session type: "active", "login", "failed", "probe"
      sort: str — "recent", "country", or "active"

    Returns:
      SessionsPageDict — sessions with total count and pagination metadata
    """
    offset = (page - 1) * per_page

    success_exists = exists().where(
        and_(AuthAttempt.session_id == Session.id, AuthAttempt.success.is_(True))
    )
    auth_exists = exists().where(AuthAttempt.session_id == Session.id)
    commands_exists = exists().where(Command.session_id == Session.id)

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

    # Same priority order as classify_category: commands > login > failed >
    # probe. Expressed as predicates here so the filter and the count agree.
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

    # Two-phase page fetch: pick the page's ids using only the sort keys, then
    # run the correlated counters over those rows alone. Counting first would
    # aggregate the whole table just to throw all but per_page rows away.
    inner_cols: list[Any] = [Session.id.label("sid")]
    inner = select(*inner_cols).outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
    if sort == "country":
        inner_order: list[Any] = [
            nulls_last(asc(GeoLocation.country)),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    elif sort == "active":
        cmd_agg = (
            select(Command.session_id, func.count().label("n"))
            .group_by(Command.session_id)
            .subquery()
        )
        sort_n = func.coalesce(cmd_agg.c.n, 0)
        inner = inner.add_columns(sort_n.label("sort_n")).outerjoin(
            cmd_agg, cmd_agg.c.session_id == Session.id
        )
        inner_order = [sort_n.desc(), Session.started_at.desc(), Session.id.desc()]
    else:  # recent
        inner_order = [Session.started_at.desc(), Session.id.desc()]
    for cond in conditions:
        inner = inner.where(cond)
    page_ids = inner.order_by(*inner_order).offset(offset).limit(per_page).subquery()

    if sort == "country":
        outer_order: list[Any] = [
            nulls_last(asc(GeoLocation.country)),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    elif sort == "active":
        outer_order = [
            page_ids.c.sort_n.desc(),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    else:
        outer_order = [Session.started_at.desc(), Session.id.desc()]

    stmt = (
        select(
            Session,
            GeoLocation,
            command_count.label("command_count"),
            auth_attempt_count.label("auth_attempt_count"),
            login_success.label("login_success"),
        )
        .join(page_ids, page_ids.c.sid == Session.id)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .order_by(*outer_order)
    )
    rows = db.execute(stmt).all()

    return {
        "sessions": [
            session_summary(
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
    """Full detail for one session, or None when no session matches."""
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
    return session_detail(session, geo)
