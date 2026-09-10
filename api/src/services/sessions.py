"""Session queries: paginated lists and per-session detail."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import and_, asc, desc, exists, func, nulls_last, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.models.ssh_client import SshClient
from src.services.serializers import session_detail, session_summary
from src.services.types import SessionDetailDict, SessionsPageDict

VALID_HAS_FILTERS = frozenset({"commands", "downloads", "success", "tcpip", "none"})

# Today's hardcoded per-key direction - order= overrides it, but omitting order
# must reproduce this exact behavior.
_SORT_DEFAULT_DIRECTION: dict[str, str] = {
    "country": "asc",
    "active": "desc",
    "interest": "desc",
    "duration": "desc",
    "recent": "desc",
}


def _sort_direction(sort: str, order: str | None) -> Callable[[Any], Any]:
    """Resolve asc()/desc() for a sort key, falling back to its default
    direction when order is not supplied. Shared by inner_order and
    outer_order so the two cannot drift apart.
    """
    resolved = order or _SORT_DEFAULT_DIRECTION[sort]
    return asc if resolved == "asc" else desc


def _has_conditions(has: str | None) -> list[Any]:
    """Turn a comma-list `has` query value into AND-ed SQL predicates.

    Unrecognized tokens, and "none" combined with any other token, are
    already rejected by the schema's has= validator before this runs, so any
    token here is a valid VALID_HAS_FILTERS member and "none" (if present)
    is the only token.
    """
    if not has:
        return []
    tokens = set(has.split(","))
    predicates: list[Any] = []
    if "commands" in tokens:
        predicates.append(Session.n_commands > 0)
    if "downloads" in tokens:
        predicates.append(Session.n_downloads > 0)
    if "success" in tokens:
        predicates.append(Session.auth_success.is_(True))
    if "tcpip" in tokens:
        predicates.append(Session.n_tcpip > 0)
    if "none" in tokens:
        predicates.append(Session.interest == 0)
    return predicates


def get_sessions_paginated(
    db: DbSession,
    page: int,
    per_page: int,
    *,
    q: str | None = None,
    country: str | None = None,
    category: str | None = None,
    sort: str = "recent",
    order: str | None = None,
    has: str | None = None,
    sha256: str | None = None,
) -> SessionsPageDict:
    """One page of session summaries, filtered and sorted in SQL.

    Country filter with sort="interest" requires a geo join, cannot use the
    interest index alone.
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
    if q:
        # Schema validates q as lowercase hex only, preventing LIKE wildcards.
        conditions.append(Session.id.like(q + "%"))
    if country:
        conditions.append(GeoLocation.country_code == country)

    # Category priority: commands > login > failed > probe (must match
    # classify_category).
    if category == "active":
        conditions.append(commands_exists)
    elif category == "login":
        conditions.append(and_(~commands_exists, success_exists))
    elif category == "failed":
        conditions.append(and_(~commands_exists, ~success_exists, auth_exists))
    elif category == "probe":
        conditions.append(and_(~commands_exists, ~auth_exists))

    conditions.extend(_has_conditions(has))

    if sha256:
        # Use EXISTS to avoid multiplying rows (sessions can have multiple
        # downloads per digest).
        conditions.append(
            exists().where(
                and_(Download.session_id == Session.id, Download.sha256 == sha256)
            )
        )

    count_stmt = (
        select(func.count(Session.id))
        .select_from(Session)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
    )
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = db.execute(count_stmt).scalar_one()

    # Unfiltered max enables consistent interest score normalization across filters.
    max_interest = db.execute(select(func.max(Session.interest))).scalar() or 0

    # Two-phase (ids then rows) avoids aggregating the entire table before limiting.
    duration_expr = func.extract(
        "epoch",
        func.coalesce(Session.ended_at, Session.started_at) - Session.started_at,
    )
    direction = _sort_direction(sort, order)

    inner_cols: list[Any] = [Session.id.label("sid")]
    inner = select(*inner_cols).outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
    if sort == "country":
        # nulls_last() in both directions: Postgres DESC defaults to NULLS
        # FIRST, which would float unresolved-country rows to the top.
        inner_order: list[Any] = [
            nulls_last(direction(GeoLocation.country)),
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
        inner_order = [direction(sort_n), Session.started_at.desc(), Session.id.desc()]
    elif sort == "interest":
        inner_order = [
            direction(Session.interest),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    elif sort == "duration":
        inner = inner.add_columns(duration_expr.label("sort_n"))
        inner_order = [
            nulls_last(direction(duration_expr)),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    else:  # recent
        inner_order = [direction(Session.started_at), Session.id.desc()]
    for cond in conditions:
        inner = inner.where(cond)
    page_ids = inner.order_by(*inner_order).offset(offset).limit(per_page).subquery()

    # (started_at desc, id desc) tiebreaker chain stays fixed for every key and
    # direction - flipping it would make pagination non-deterministic.
    if sort == "country":
        outer_order: list[Any] = [
            nulls_last(direction(GeoLocation.country)),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    elif sort == "active" or sort == "duration":
        outer_order = [
            nulls_last(direction(page_ids.c.sort_n)),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    elif sort == "interest":
        outer_order = [
            direction(Session.interest),
            Session.started_at.desc(),
            Session.id.desc(),
        ]
    else:
        outer_order = [direction(Session.started_at), Session.id.desc()]

    stmt = (
        select(
            Session,
            GeoLocation,
            SshClient.client_version,
            command_count.label("command_count"),
            auth_attempt_count.label("auth_attempt_count"),
            login_success.label("login_success"),
        )
        .join(page_ids, page_ids.c.sid == Session.id)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .outerjoin(SshClient, SshClient.session_id == Session.id)
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
                client_version=cv,
            )
            for s, g, cv, cc, ac, ls in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "max_interest": max_interest,
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
