"""The ordered snapshot: the ids in a view, in sort order, as of a moment.

Shared by the layout pass and the page queries so the two cannot disagree about
which rows are in the view or how they are ordered.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, func

from src.models.session import Session
from src.models.ssh_client import SshClient
from src.services.sessions.filters import SortKey, order_clauses, ordered_ids

# ingest lag moves a close in or out of a snapshot by about this much.
_SETTLE = timedelta(minutes=1)


def story(authed: Any, as_of: datetime) -> Any:
    """Per-session story hash out of: counters, outcome, client banner.
    `authed` says whether it tried a login.

    Only settled sessions (ended at least _SETTLE before `as_of`) hash their story
    based on sessions' results. Otherwise hash is generated based on the Session.id,
    which is unique.
    """

    # all sessions ended eariler than as_of reduced by _SETTLE
    settled = Session.ended_at <= as_of - _SETTLE

    # hashing the generated text with seed 0
    story = func.hashtextextended(
        # results in something like: 0|0|0|false|true|SSH-2.0-Go
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

    # in case when session was settled, generate the hash based on the results
    # otherwise - based on the session id
    # because of this - matching ids are introduced for identical settled sessions,
    # while hashing based on the unique id will be unique
    return case((settled, story), else_=func.hashtextextended(Session.id, 1))


def ordered_window(
    conditions: list[Any], sort: str, order: str | None, as_of: datetime
) -> tuple[Select[Any], list[SortKey]]:
    """The snapshot's ordered ids: everything matching that started by as_of."""
    # query with the sorting by keys returned in the second tuple
    inner, keys = ordered_ids(sort, order)

    # constraining the entire sorted query by the conditions
    # filtering conditions have a single source of truth in
    # categories.py::SESSION_CATEGORY and are composed by filters.py::filter_conditions
    stmt = inner.where(*conditions, Session.started_at <= as_of)

    # applying the sorting on the constrained query
    # keys were already added to the main SELECT in filters.py::ordered_ids
    return stmt.order_by(*order_clauses([k[0] for k in keys], keys)), keys
