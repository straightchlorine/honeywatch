"""The public session read paths: paginated, folded, run members, and detail."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.models.ssh_client import SshClient
from src.services.serializers import session_detail, session_summary
from src.services.sessions.cache import cached_layout
from src.services.sessions.checkpoints import checkpoint_seek
from src.services.sessions.filters import (
    SORT_DEFAULT_DIRECTION,
    filter_conditions,
    order_clauses,
    ordered_ids,
)
from src.services.sessions.folding import fold
from src.services.sessions.layout import build_layout
from src.services.sessions.window import ordered_window, story
from src.services.types import (
    FoldedPageDict,
    FoldedSessionDict,
    RunMembersPageDict,
    SessionDetailDict,
    SessionsPageDict,
    SessionSummaryDict,
)


def _summaries(db: DbSession, ids: Any, order: list[Any]) -> list[SessionSummaryDict]:
    """Summaries for the sessions in the `ids` subquery (column `sid`)."""
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
    stmt = (
        select(
            Session,
            GeoLocation,
            SshClient.client_version,
            command_count.label("command_count"),
            auth_attempt_count.label("auth_attempt_count"),
            login_success.label("login_success"),
        )
        .join(ids, ids.c.sid == Session.id)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .outerjoin(SshClient, SshClient.session_id == Session.id)
        .order_by(*order)
    )
    return [
        session_summary(
            s,
            g,
            command_count=cc,
            auth_attempt_count=ac,
            login_success=ls,
            client_version=cv,
        )
        for s, g, cv, cc, ac, ls in db.execute(stmt).all()
    ]


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
    conditions = filter_conditions(
        q=q, country=country, category=category, has=has, sha256=sha256
    )
    count_stmt = (
        select(func.count(Session.id))
        .select_from(Session)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        .where(*conditions)
    )
    total = db.execute(count_stmt).scalar_one()

    # Two-phase (ids then rows) avoids aggregating the entire table before limiting.
    inner, keys = ordered_ids(sort, order)
    page_ids = (
        inner.where(*conditions)
        .order_by(*order_clauses([k[0] for k in keys], keys))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .subquery()
    )
    order_cols = [page_ids.c[f"o{i}"] for i in range(len(keys))]
    return {
        "sessions": _summaries(db, page_ids, order_clauses(order_cols, keys)),
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "max_interest": _max_interest(db),
    }


def get_sessions_folded(
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
) -> FoldedPageDict:
    """One page of display rows: runs of look-alike sessions fold into their
    first session, so every page but the last holds exactly per_page rows.

    Known limit:
    Page query loads every member of each run on the page, not per_page rows
    (largest seen on prod data: 1.3k sessions by recency, 15k by country).
    The main cost then was the OFFSET walk. This is now replaced with new checkpoint
    keyset seek.

    Summarizing runs in SQL along seems like it would buy little still.
    TODO: disprove/prove
    """
    # resolve the sorting directions
    resolved = order or SORT_DEFAULT_DIRECTION[sort]

    # build the list of conditiosn, constraining the query
    conditions = filter_conditions(
        q=q, country=country, category=category, has=has, sha256=sha256
    )

    # get the currently served layout
    layout = cached_layout(
        db,
        (q, country, category, has, sha256, sort, resolved),
        lambda d: build_layout(d, conditions, sort, resolved),
    )

    # if unable to serve - provide regular pagination
    if layout is None:
        plain = get_sessions_paginated(
            db,
            page,
            per_page,
            q=q,
            country=country,
            category=category,
            sort=sort,
            order=resolved,
            has=has,
            sha256=sha256,
        )
        return {
            **plain,
            "sessions": [{**s, "run": None} for s in plain["sessions"]],
            "as_of": datetime.now(timezone.utc),
        }

    # page count of the display rows
    pages = -(-layout.rows // per_page)
    items: list[FoldedSessionDict] = []

    if page <= pages:
        # row boundaries - low and high
        # converting the display rows into genuine snapshot positions
        lo = layout.offset((page - 1) * per_page)
        hi = layout.offset(min(page * per_page, layout.rows))

        # ordered sessions, with their stories as well as the checkpoint
        stmt, keys = ordered_window(conditions, sort, resolved, layout.as_of)
        seek = checkpoint_seek(db, layout, lo, sort, resolved, keys)

        if seek is None:
            # regular walk
            page_ids = stmt.offset(lo).limit(hi - lo).subquery()
        else:
            # after narrows the snapshot to the rows that sort after the checkpoint
            # session
            # local_lo is how many rows sepaerate the row right after the the checkpoint
            # from the page's first row
            after, local_lo = seek
            page_ids = stmt.where(after).offset(local_lo).limit(hi - lo).subquery()

        # tried to log in flag story()
        authed = exists().where(AuthAttempt.session_id == Session.id)
        # sort-key columns on the subquery - for the ORDER BY
        order_cols = [page_ids.c[f"o{i}"] for i in range(len(keys))]

        rows = db.execute(
            select(
                page_ids.c.sid,
                # recompute each row's story with current layout's as_of
                # (same instant as layout did)
                story(authed, layout.as_of).label("story"),
                GeoLocation.country_code,
                GeoLocation.country,
                Session.started_at,
                Session.ended_at,
            )
            .join(Session, Session.id == page_ids.c.sid)
            .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
            .outerjoin(SshClient, SshClient.session_id == Session.id)
            # ensuring joins preserve order
            .order_by(*order_clauses(order_cols, keys))
        ).all()

        # walks the rows and groups consecutive equal stories
        # RUN_MIN or more required for the grouping
        folded = fold(rows, lo)

        # id list of the visible sessions only
        ids = select(Session.id.label("sid")).where(
            Session.id.in_([sid for sid, _ in folded])
        )
        # full summaries, including command counts, login results ang geo
        by_id = {s["id"]: s for s in _summaries(db, ids.subquery(), [])}

        # walk folded display in order, looking up each summary
        items = [{**by_id[sid], "run": run} for sid, run in folded if sid in by_id]

    return {
        "sessions": items,
        "total": layout.total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "max_interest": _max_interest(db),
        "as_of": layout.as_of,
    }


def get_run_members(
    db: DbSession,
    page: int,
    per_page: int,
    *,
    as_of: datetime,
    offset: int,
    count: int,
    q: str | None = None,
    country: str | None = None,
    category: str | None = None,
    sort: str = "recent",
    order: str | None = None,
    has: str | None = None,
    sha256: str | None = None,
) -> RunMembersPageDict:
    """One page of a run's sessions: rows offset..offset+count of the folded
    list's snapshot, so the request repeats that list's filters and as_of.
    """
    conditions = filter_conditions(
        q=q, country=country, category=category, has=has, sha256=sha256
    )
    skip = (page - 1) * per_page
    limit = max(0, min(per_page, count - skip))
    sessions: list[SessionSummaryDict] = []
    if limit:
        stmt, keys = ordered_window(conditions, sort, order, as_of)
        page_ids = stmt.offset(offset + skip).limit(limit).subquery()
        order_cols = [page_ids.c[f"o{i}"] for i in range(len(keys))]
        sessions = _summaries(db, page_ids, order_clauses(order_cols, keys))
    return {
        "sessions": sessions,
        "total": count,
        "page": page,
        "per_page": per_page,
        "pages": (count + per_page - 1) // per_page,
    }


def _max_interest(db: DbSession) -> int:
    # Unfiltered, so scores normalize the same across filters, pages and deep links.
    return db.execute(select(func.max(Session.interest))).scalar() or 0


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
    return session_detail(session, geo, _max_interest(db))
