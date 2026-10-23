"""Seeking into a layout by keyset instead of walking an OFFSET.

A deep page that walks its OFFSET makes the planner sort and emit every skipped
row; seeking from a checkpoint at most _CHECKPOINT_EVERY rows back keeps the
page query's sort small. See RESULTS.md E4.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, false, or_
from sqlalchemy.orm import Session as DbSession

from src.models.session import Session
from src.services.sessions.filters import SortKey
from src.services.sessions.layout import Layout
from src.services.sessions.window import ordered_window


def _after_key(expr: Any, value: Any, descending: bool, nulls_last: bool) -> Any:
    """SQL for "expr sorts strictly after `value`" under one key's direction."""
    if value is None:
        # NULL is first or last for this key: nothing sorts after the last one,
        # and every non-NULL sorts after the first one.
        return false() if nulls_last else expr.is_not(None)
    if not nulls_last:
        return expr < value if descending else expr > value
    # NULLS LAST: a NULL sorts after every non-NULL, so it is always "after".
    return or_(expr.is_(None), expr < value if descending else expr > value)


def _after_checkpoint(keys: list[SortKey], values: Sequence[Any]) -> Any:
    """SQL for "this row's key tuple sorts strictly after the checkpoint row's".

    Every sort ends in (started_at DESC, id DESC) and ids are unique, so the key
    tuple is a total order: the rows strictly after a checkpoint are exactly the
    rows that followed the checkpoint's position. That is what lets a keyset seek
    replace an OFFSET without changing which rows come back.
    """
    # or branches
    clauses: list[Any] = []
    # ties so far
    equal: list[Any] = []

    # unpack the keys and corresponding values of this single pulled session
    for (expr, direction, nulls_last_key), value in zip(keys, values, strict=True):
        # comparison query - for one key, against the key's checkpoint value
        after = _after_key(expr, value, direction is desc, nulls_last_key)

        # save the OR branches of those comparisons
        # if ties were observed, spread the list and convert to:
        # column IS NOT DISTINCT FROM value AND ... AND after condition
        # with each iteration it carries tied records over to the next one
        # next one only needs to consider those that are not in order,
        # that's why AND constrains this set
        clauses.append(and_(*equal, after) if equal else after)

        # if ties for sorting were found - resolve in the next key
        equal.append(expr.is_not_distinct_from(value))
    return or_(*clauses)


def _checkpoint_values(
    db: DbSession, sort: str, order: str | None, as_of: datetime, sid: str
) -> list[Any] | None:
    """One session's sort-key values, in key order; None if it is not there.

    Uses the same ordered_window the page uses, so the values are exactly the
    ones the ordering was built from.
    """
    stmt, keys = ordered_window([Session.id == sid], sort, order, as_of)
    row = db.execute(stmt.limit(1)).first()
    if row is None:
        return None
    # i + 1 since the column 0 is the sid
    return [row[i + 1] for i in range(len(keys))]


def checkpoint_seek(
    db: DbSession,
    layout: Layout,
    lo: int,
    sort: str,
    order: str | None,
    keys: list[SortKey],
) -> tuple[Any, int] | None:
    """(keyset predicate, local offset) to use instead of snapshot offset `lo`.

    None means "keep the plain OFFSET": there is no checkpoint before `lo`, or
    its session has gone. The local offset stays under _CHECKPOINT_EVERY, which
    is what keeps the page query's sort small.
    """
    # find the nearest checkpint above lo (pos, sid)
    # in case none - use regular OFFSET
    checkpoint = layout.checkpoint_before(lo)
    if checkpoint is None:
        return None

    # query this session id and get it's sort-key values
    # those are checkpoints values
    pos, sid = checkpoint
    values = _checkpoint_values(db, sort, order, layout.as_of, sid)

    # none if session was deleted
    if values is None:
        return None

    # build the query and return positions
    return _after_checkpoint(keys, values), lo - pos - 1
