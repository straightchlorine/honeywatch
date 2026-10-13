"""Session queries: paginated and folded lists, and per-session detail."""

from __future__ import annotations

import logging
import threading
import time
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import accumulate
from typing import Any

from sqlalchemy import (
    Row,
    Select,
    and_,
    asc,
    desc,
    exists,
    func,
    nulls_last,
    select,
    text,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload, sessionmaker

from src.extensions import get_session_factory
from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.models.ssh_client import SshClient
from src.services.serializers import session_detail, session_summary
from src.services.types import (
    FoldedPageDict,
    FoldedSessionDict,
    RunDict,
    RunMembersPageDict,
    SessionDetailDict,
    SessionsPageDict,
    SessionSummaryDict,
)

_log = logging.getLogger(__name__)

VALID_HAS_FILTERS = frozenset({"commands", "downloads", "success", "tcpip", "none"})

# Default direction per sort key, matching the old hardcoded behavior.
# order= overrides this; omitting it must still match exactly.
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


def _filter_conditions(
    *,
    q: str | None,
    country: str | None,
    category: str | None,
    has: str | None,
    sha256: str | None,
) -> list[Any]:
    success_exists = exists().where(
        and_(AuthAttempt.session_id == Session.id, AuthAttempt.success.is_(True))
    )
    auth_exists = exists().where(AuthAttempt.session_id == Session.id)
    commands_exists = exists().where(Command.session_id == Session.id)

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
    return conditions


# One sort key: expression, asc/desc, NULLS LAST.
_SortKey = tuple[Any, Callable[[Any], Any], bool]


def _ordered(sort: str, order: str | None) -> tuple[Select[Any], list[_SortKey]]:
    """Geo-joined id select exposing its sort keys as o0..oN, plus the keys.

    The (started_at desc, id desc) tiebreaker chain stays fixed for every key
    and direction - flipping it would make pagination non-deterministic.
    """
    direction = _sort_direction(sort, order)
    stmt = select(Session.id.label("sid")).outerjoin(
        GeoLocation, GeoLocation.ip == Session.src_ip
    )
    tail: list[_SortKey] = [
        (Session.started_at, desc, False),
        (Session.id, desc, False),
    ]
    if sort == "country":
        # NULLS LAST in both directions: Postgres DESC defaults to NULLS
        # FIRST, which would float unresolved-country rows to the top.
        keys = [(GeoLocation.country, direction, True), *tail]
    elif sort == "active":
        cmd_agg = (
            select(Command.session_id, func.count().label("n"))
            .group_by(Command.session_id)
            .subquery()
        )
        stmt = stmt.outerjoin(cmd_agg, cmd_agg.c.session_id == Session.id)
        keys = [(func.coalesce(cmd_agg.c.n, 0), direction, False), *tail]
    elif sort == "interest":
        keys = [(Session.interest, direction, False), *tail]
    elif sort == "duration":
        duration = func.extract(
            "epoch",
            func.coalesce(Session.ended_at, Session.started_at) - Session.started_at,
        )
        keys = [(duration, direction, True), *tail]
    else:  # recent
        keys = [(Session.started_at, direction, False), (Session.id, desc, False)]
    stmt = stmt.add_columns(*(k[0].label(f"o{i}") for i, k in enumerate(keys)))
    return stmt, keys


def _order_by(cols: Sequence[Any], keys: list[_SortKey]) -> list[Any]:
    return [
        nulls_last(d(c)) if last else d(c)
        for c, (_, d, last) in zip(cols, keys, strict=True)
    ]


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
    conditions = _filter_conditions(
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
    inner, keys = _ordered(sort, order)
    page_ids = (
        inner.where(*conditions)
        .order_by(*_order_by([k[0] for k in keys], keys))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .subquery()
    )
    order_cols = [page_ids.c[f"o{i}"] for i in range(len(keys))]
    return {
        "sessions": _summaries(db, page_ids, _order_by(order_cols, keys)),
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "max_interest": _max_interest(db),
    }


# A run is RUN_MIN or more consecutive sessions (in the requested order) that
# share a story: what the dashboard shows as one row, "N more like this".
RUN_MIN = 3

# Page boundaries cost a full ordered pass, so they are cached per filter set
# and sort, for any per_page. A stale entry is still served (its as_of snapshot
# keeps it consistent) while a background thread rebuilds it.
_LAYOUT_TTL_S = 60.0
_LAYOUT_CACHE_SIZE = 64

# One pass at a time per process: concurrent passes run Postgres out of
# shared memory. A request that cannot get the slot in time gets the plain list.
_LAYOUT_WAIT_S = 5.0
_build_slot = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class _Layout:
    as_of: datetime
    total: int
    # Per run, in order: display rows above its row, and the sessions folded
    # away by it and every run before it.
    rows_before: list[int]
    hidden: list[int]
    built_at: float

    @property
    def rows(self) -> int:
        return self.total - (self.hidden[-1] if self.hidden else 0)

    def offset(self, row: int) -> int:
        """Snapshot offset of the session shown as display row `row`."""
        i = bisect_right(self.rows_before, row) - 1
        if i < 0:
            return row
        if self.rows_before[i] == row:
            return row + (self.hidden[i - 1] if i else 0)
        return row + self.hidden[i]


_layouts: OrderedDict[tuple[Any, ...], _Layout] = OrderedDict()
_layouts_lock = threading.Lock()
_rebuilding: set[tuple[Any, ...]] = set()
_building: dict[tuple[Any, ...], threading.Event] = {}


def clear_layout_cache() -> None:
    with _layouts_lock:
        _layouts.clear()


def _store_layout(key: tuple[Any, ...], layout: _Layout) -> _Layout:
    with _layouts_lock:
        _layouts[key] = layout
        _layouts.move_to_end(key)
        while len(_layouts) > _LAYOUT_CACHE_SIZE:
            _layouts.popitem(last=False)
    return layout


def _build_in_slot(
    db: DbSession, build: Callable[[DbSession], _Layout], wait: float
) -> _Layout | None:
    """Run build in the process's one slot; None if busy past `wait` or failed.

    A failure (parallel workers out of shared memory) retries once serially.
    """
    if not _build_slot.acquire(timeout=wait):
        return None
    try:
        try:
            return build(db)
        except OperationalError:
            db.rollback()
            _log.warning("session layout pass failed, retrying serially")
            db.execute(text("SET LOCAL max_parallel_workers_per_gather = 0"))
            return build(db)
    except OperationalError:
        db.rollback()
        _log.exception("session layout pass failed")
        return None
    finally:
        _build_slot.release()


def _rebuild_layout(
    key: tuple[Any, ...],
    build: Callable[[DbSession], _Layout],
    factory: sessionmaker[DbSession],
) -> None:
    try:
        with factory() as db:
            layout = _build_in_slot(db, build, 0)
        if layout is not None:
            _store_layout(key, layout)
    except Exception:
        _log.exception("session layout rebuild failed")
    finally:
        with _layouts_lock:
            _rebuilding.discard(key)


def _cached_layout(
    db: DbSession, key: tuple[Any, ...], build: Callable[[DbSession], _Layout]
) -> _Layout | None:
    """The key's layout, or None when it cannot be built now."""
    with _layouts_lock:
        hit = _layouts.get(key)
        if hit is not None:
            _layouts.move_to_end(key)
        stale = (
            hit is not None
            and time.monotonic() - hit.built_at > _LAYOUT_TTL_S
            and key not in _rebuilding
        )
        if stale:
            _rebuilding.add(key)
        # Single flight: one request builds a missing layout, the rest wait for it.
        leader = follow = None
        if hit is None:
            follow = _building.get(key)
            if follow is None:
                leader = _building[key] = threading.Event()
    if follow is not None:
        follow.wait(_LAYOUT_WAIT_S * 2)
        with _layouts_lock:
            return _layouts.get(key)
    if leader is not None:
        try:
            layout = _build_in_slot(db, build, _LAYOUT_WAIT_S)
            return None if layout is None else _store_layout(key, layout)
        finally:
            with _layouts_lock:
                del _building[key]
            leader.set()
    if stale:
        threading.Thread(
            target=_rebuild_layout,
            args=(key, build, get_session_factory()),
            daemon=True,
        ).start()
    return hit


def _story(authed: Any) -> Any:
    """Per-session story hash: the fields the rows show - counters (and so
    interest), outcome, client banner. `authed` says whether it tried a login.

    Needs SshClient joined.

    Known limit:
    Live counters are counted, so a session still open when a layout was built
    can change story before the page query re-hashes it.
    It shifts the page by a row or splits/merges a run at its edge. For the new
    performance patch - only ended sessions should be hashed.
    """
    return func.hashtextextended(
        func.concat_ws(
            "|",
            Session.n_commands,
            Session.n_downloads,
            Session.n_tcpip,
            Session.auth_success,
            authed,
            SshClient.client_version,
        ),
        0,
    )


def _ordered_window(
    conditions: list[Any], sort: str, order: str | None, as_of: datetime
) -> tuple[Select[Any], list[_SortKey]]:
    """The snapshot's ordered ids: everything matching that started by as_of."""
    inner, keys = _ordered(sort, order)
    stmt = inner.where(*conditions, Session.started_at <= as_of)
    return stmt.order_by(*_order_by([k[0] for k in keys], keys)), keys


def _build_layout(
    db: DbSession, conditions: list[Any], sort: str, order: str | None
) -> _Layout:
    as_of = datetime.now(timezone.utc)
    stmt, keys = _ordered_window(conditions, sort, order, as_of)
    # Joined, not EXISTS per row: over the whole table one hash beats 800k probes.
    authed = select(AuthAttempt.session_id).distinct().subquery()
    k = (
        stmt.add_columns(_story(authed.c.session_id.is_not(None)).label("story"))
        .outerjoin(SshClient, SshClient.session_id == Session.id)
        .outerjoin(authed, authed.c.session_id == Session.id)
        .subquery("k")
    )
    window = _order_by([k.c[f"o{i}"] for i in range(len(keys))], keys)
    b = select(
        (func.row_number().over(order_by=window) - 1).label("pos"),
        func.count().over().label("total"),
        k.c.story.is_distinct_from(func.lag(k.c.story).over(order_by=window)).label(
            "brk"
        ),
    ).subquery("b")
    isl = (
        select(
            b.c.pos,
            b.c.total,
            (
                func.coalesce(func.lead(b.c.pos).over(order_by=b.c.pos), b.c.total)
                - b.c.pos
            ).label("size"),
        )
        .where(b.c.brk)
        .subquery("isl")
    )
    is_run = isl.c.size >= RUN_MIN
    starts, sizes, total = db.execute(
        select(
            func.array_agg(isl.c.pos).filter(is_run),
            func.array_agg(isl.c.size).filter(is_run),
            func.max(isl.c.total),
        )
    ).one()
    runs = sorted(zip(starts or [], sizes or [], strict=True))
    hidden = list(accumulate(n - 1 for _, n in runs))
    rows_before = [pos - h + n - 1 for (pos, n), h in zip(runs, hidden, strict=True)]
    return _Layout(
        as_of=as_of,
        total=total or 0,
        rows_before=rows_before,
        hidden=hidden,
        built_at=time.monotonic(),
    )


def _run_summary(members: Sequence[Row[Any]], offset: int) -> RunDict:
    countries = {r.country_code: r.country for r in members if r.country_code}
    secs = [
        round((r.ended_at - r.started_at).total_seconds())
        for r in members
        if r.ended_at is not None and r.ended_at >= r.started_at
    ]
    starts = [r.started_at for r in members]
    only = next(iter(countries.items())) if len(countries) == 1 else (None, None)
    return {
        "count": len(members),
        "offset": offset,
        "countries": len(countries),
        "country_code": only[0],
        "country": only[1],
        "min_duration_s": min(secs, default=None),
        "max_duration_s": max(secs, default=None),
        "oldest": min(starts),
        "newest": max(starts),
    }


def _fold(rows: Sequence[Row[Any]], offset: int) -> list[tuple[str, RunDict | None]]:
    """Display rows of a page: (session id, its run or None), in order."""
    out: list[tuple[str, RunDict | None]] = []
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and rows[j].story == rows[i].story:
            j += 1
        if j - i >= RUN_MIN:
            out.append((rows[i].sid, _run_summary(rows[i + 1 : j], offset + i + 1)))
        else:
            out.extend((r.sid, None) for r in rows[i:j])
        i = j
    return out


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
    (largest is around 1,2k sessions).
    It is bounded, but should be optimized in the incoming performance patch.
    Runs should be summarized in SQL instead of _fold.
    """
    resolved = order or _SORT_DEFAULT_DIRECTION[sort]
    conditions = _filter_conditions(
        q=q, country=country, category=category, has=has, sha256=sha256
    )
    layout = _cached_layout(
        db,
        (q, country, category, has, sha256, sort, resolved),
        lambda d: _build_layout(d, conditions, sort, resolved),
    )
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
    pages = -(-layout.rows // per_page)
    items: list[FoldedSessionDict] = []
    if page <= pages:
        lo = layout.offset((page - 1) * per_page)
        hi = layout.offset(min(page * per_page, layout.rows))
        stmt, keys = _ordered_window(conditions, sort, resolved, layout.as_of)
        page_ids = stmt.offset(lo).limit(hi - lo).subquery()
        authed = exists().where(AuthAttempt.session_id == Session.id)
        rows = db.execute(
            select(
                page_ids.c.sid,
                _story(authed).label("story"),
                GeoLocation.country_code,
                GeoLocation.country,
                Session.started_at,
                Session.ended_at,
            )
            .join(Session, Session.id == page_ids.c.sid)
            .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
            .outerjoin(SshClient, SshClient.session_id == Session.id)
            .order_by(*_order_by([page_ids.c[f"o{i}"] for i in range(len(keys))], keys))
        ).all()
        folded = _fold(rows, lo)
        ids = select(Session.id.label("sid")).where(
            Session.id.in_([sid for sid, _ in folded])
        )
        by_id = {s["id"]: s for s in _summaries(db, ids.subquery(), [])}
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
    conditions = _filter_conditions(
        q=q, country=country, category=category, has=has, sha256=sha256
    )
    skip = (page - 1) * per_page
    limit = max(0, min(per_page, count - skip))
    sessions: list[SessionSummaryDict] = []
    if limit:
        stmt, keys = _ordered_window(conditions, sort, order, as_of)
        page_ids = stmt.offset(offset + skip).limit(limit).subquery()
        order_cols = [page_ids.c[f"o{i}"] for i in range(len(keys))]
        sessions = _summaries(db, page_ids, _order_by(order_cols, keys))
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
