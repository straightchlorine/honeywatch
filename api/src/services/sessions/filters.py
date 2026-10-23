"""Filtering and ordering for the session list queries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import Select, and_, asc, desc, exists, func, nulls_last, select

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session

# default direction per sort key; order= overrides this
SORT_DEFAULT_DIRECTION: dict[str, str] = {
    "country": "asc",
    "active": "desc",
    "interest": "desc",
    "duration": "desc",
    "recent": "desc",
}


def _sort_direction(sort: str, order: str | None) -> Callable[[Any], Any]:
    """Resolve asc()/desc() for a sort key, falling back to its default
    direction when order is not supplied.

    Shared by inner_order and outer_order.
    """
    resolved = order or SORT_DEFAULT_DIRECTION[sort]
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


def filter_conditions(
    *,
    q: str | None,
    country: str | None,
    category: str | None,
    has: str | None,
    sha256: str | None,
) -> list[Any]:
    """Build list of conditions that can be given to constraint a query."""

    # did this session attempt to log in?
    # implies at least one row in auth_attempts
    auth_exists = exists().where(AuthAttempt.session_id == Session.id)

    # did this session log in successfuly?
    # implies at least one row in auth_attempts table with success set to true
    success_exists = exists().where(
        and_(AuthAttempt.session_id == Session.id, AuthAttempt.success.is_(True))
    )

    # did this session log in successfuly and executed commands?
    # implies at least one row for this session in commands
    # (that also follows that it has a row in auth_attempts with success=true)
    commands_exists = exists().where(Command.session_id == Session.id)

    # TODO: type it - it's BinaryExpression/BooleanClauseList
    # so the type would be ColumnElement[bool], but do it everywhere in one pass
    conditions: list[Any] = []

    # this is the query from the text box; it's validated in the request schema
    if q:
        # schema validates q as lowercase hex only, preventing LIKE wildcards.
        conditions.append(Session.id.like(q + "%"))

    # constrain by the country
    if country:
        conditions.append(GeoLocation.country_code == country)

    # priority: commands > login > failed > probe (must match classify_category)
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
        # EXISTS: no multiplying rows (multiple downloads per digest)
        conditions.append(
            exists().where(
                and_(Download.session_id == Session.id, Download.sha256 == sha256)
            )
        )
    return conditions


# sort key: expression, asc/desc, NULLS LAST.
SortKey = tuple[Any, Callable[[Any], Any], bool]


def ordered_ids(sort: str, order: str | None) -> tuple[Select[Any], list[SortKey]]:
    """Geo-joined id select exposing its sort keys as o0..oN, plus the keys.

    `o` in the sort keys stands for ordering - the number corresponds to the priority.

    The (started_at desc, id desc) tiebreaker chain stays fixed for every key
    and direction - flipping it would make pagination non-deterministic.
    """
    direction = _sort_direction(sort, order)

    # get all sessions, matching their geo location (or nulls)
    stmt = select(Session.id.label("sid")).outerjoin(
        GeoLocation, GeoLocation.ip == Session.src_ip
    )

    # tiebreaker sort keys
    tail: list[SortKey] = [
        (Session.started_at, desc, False),  # newest first among ties
        # to ensure all ties are broken consistently
        # (duplicates the `sid` set above, since it's responsible for joins)
        (Session.id, desc, False),
    ]

    # depending on the sort build the keys table, including the tail at the end
    if sort == "country":
        # NULLS LAST for both directions:
        # DESC defaults to NULLS FIRST, would put unresolved-country rows on top
        keys = [(GeoLocation.country, direction, True), *tail]
    elif sort == "active":
        # table such that
        # session_id | n
        # where n is the number of command given session executed
        cmd_agg = (
            select(Command.session_id, func.count().label("n"))
            .group_by(Command.session_id)
            .subquery()
        )

        # putting the table above as another outer join, matching on already
        # present `sid` on the left
        stmt = stmt.outerjoin(cmd_agg, cmd_agg.c.session_id == Session.id)
        # ^ this query looks someting like this:
        # sid | count(commands) | started_at | session_id
        # last two are the tiebreakers

        # ensuring that column output of the cmd_agg, concretely the count of
        # commands labeled as n is numerical; eliminates nulls
        keys = [(func.coalesce(cmd_agg.c.n, 0), direction, False), *tail]
    elif sort == "interest":
        keys = [(Session.interest, direction, False), *tail]
    elif sort == "duration":
        duration = func.extract(
            "epoch",
            # in case null, replacing with started_at -> duration = 0
            func.coalesce(Session.ended_at, Session.started_at) - Session.started_at,
        )

        # the last true - here we don't have nulls, so it does not impact
        # keeping for consistency/guard
        keys = [(duration, direction, True), *tail]
    else:  # recent
        keys = [(Session.started_at, direction, False), (Session.id, desc, False)]

    # adding columns the final query will be sorted by
    # for each key `k` with index `i`, add it as a column to the main query
    # and label it as f'o{i}', where o stands for ordering
    stmt = stmt.add_columns(*(k[0].label(f"o{i}") for i, k in enumerate(keys)))
    return stmt, keys


def order_clauses(cols: Sequence[Any], keys: list[SortKey]) -> list[Any]:
    """Helper to unpack selected SortKeys gathered by filters.py::ordered_ids."""
    return [
        nulls_last(d(c)) if last else d(c)
        for c, (_, d, last) in zip(cols, keys, strict=True)
    ]
