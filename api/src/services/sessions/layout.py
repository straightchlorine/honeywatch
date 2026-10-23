"""Folding runs in a session list and how to find them.

The folded list shows a run (RUN_MIN or more consecutive sessions with the
same story, see window.story) as one display row.
Whether two sessions are consecutive depends on the whole ordered view, so a page
cannot be served from its own rows.

It records:

    - run starts and sizes, compressed into `rows_before` / `hidden`, which turn a
    display row number into a snapshot offset;
    - `checkpoints`, one session id every _CHECKPOINT_EVERY snapshot rows, so a
    deep page can seek by keyset instead of walking a large OFFSET;
    - `as_of`, the snapshot moment the pass and every page served from it share.

Naming convention:

    - run/island - RUN_MIN or more consecutive snapshots with the same story
    - fold - collapsing a run/island into a single display row with "+n more"
"""

from __future__ import annotations

import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import accumulate
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.session import Session
from src.models.ssh_client import SshClient
from src.services.sessions.common import RUN_MIN
from src.services.sessions.filters import order_clauses
from src.services.sessions.window import ordered_window, story

# Checkpoint spacing, in snapshot rows.
#
# Optimization problem:
# Page deep in the list is `LIMIT n OFFSET m`, and Postgres cannot skip those m
# rows - sorts and emits them anyway, so the planner's sort is bounded at m + n rows.
#
# On the country sort's largest-run page (OFFSET 322,518 LIMIT 20,165) this causes
# a *50 MB external merge sort* to return 20,165 rows, required for every request
# of that page.
#
# Optimization:
# Layout pass already walks the whole ordered view. It remembers which session is
# at positions 0, 1000, 2000, ... The page then:
#   1. takes the last checkpoint before its offset,
#   2. looks up that session's sort-key values by primary key
#   3. adds a WHERE that keeps only the rows the ORDER BY places after the checkpoint
# What remains is an OFFSET of at most _CHECKPOINT_EVERY - 1 rows, so the sort is a
# bounded top-N heapsort over a page's worth of rows (39 kB on the deep page) instead
# of a disk merge over everything above it.
_CHECKPOINT_EVERY = 1000


@dataclass(frozen=True)
class Layout:
    """One ordered view's fold geometry, as of a moment.

    Immutable: cache hands the same instance to every request thread and keeps
    serving a stale one while a replacement is built.

    Positions come in two flavours, and the whole class is about converting
    between them:

    Two positions are used:

    - a snapshot offset:
        a session's 0-based position in the ordered view, i.e. all positions
        hidden or not: a number an OFFSET clause can use
    - a display row:
        a 0-based position in the folded list the client sees

    Example:
    10 sessions, one island of 4 at snapshot positions 2..5.
    The folded list has 7 rows.
    Display rows 0..2 are snapshot 0..2 (row 2 is the run).
    Display row 3 is snapshot 6, since the 3 other run members are hidden behind row 2.

    0 1 [2 3 4 5] 6 7 [8 9 10] 11
         ^-hidden ^-next display row

    The runs are stored as two parallel lists in snapshot order, one entry per run.
    Both are cumulative, so bisect answers:
    "how many sessions are hidden above this point?" without summing:

    - `rows_before[i]` is the display row the i-th run occupies, which equals
        the number of display rows above it;
    - `hidden[i]` is the number of sessions hidden by the i-th run and every
        run before it (each run of n hides n - 1).

    In the example: rows_before = [2], hidden = [3].
    """

    as_of: datetime
    total: int
    rows_before: list[int]
    hidden: list[int]

    # time.monotonic() at build time; cache compares against the same clock for TTL
    built_at: float

    # (snapshot position, session id) at positions 0, _CHECKPOINT_EVERY,
    # 2 * _CHECKPOINT_EVERY, ..., ascending
    checkpoints: list[tuple[int, str]]

    @property
    def rows(self) -> int:
        """Display rows in the folded list: every session, minus the ones folded
        away. `hidden` is cumulative, so its last entry is the grand total."""
        return self.total - (self.hidden[-1] if self.hidden else 0)

    def checkpoint_before(self, pos: int) -> tuple[int, str] | None:
        """The last checkpoint strictly before snapshot offset `pos`, if any.

        1. Receive any position from the snapshot (entire result).
        2. Find between which checkpoints this position resides.
        3. Pick previous one, such that local offset counts from that point.

        Excludes the checkpoint row itself. The page applies local offset:

        `pos - checkpoint - 1`.

        If checkpoint was at `pos` it would be -1 - skipped in favour of the one
        before it.
        """
        if pos <= 0 or not self.checkpoints:
            return None

        # Tuples compare lexicographically, so a shorter prefix sorts first:
        # (pos,) < (pos, sid) for any sid.
        # bisect_left lands on the first checkpoint at or past `pos`.
        # The one before it is the answer.
        i = bisect_left(self.checkpoints, (pos,)) - 1
        return self.checkpoints[i] if i >= 0 else None

    def offset(self, row: int) -> int:
        """Translating the rows into the pages within the snapshot.

        Returns the snapshot offset of the session shown as display row.
        It's the display row plus every session hidden above it. In this example:

            0 1 [2 3 4 5] 6 7 [8 9 10] 11
                 ^-hidden ^-next display row

        2 has only 2 rows above.
        Second island starts at 8. There we have:

        8 (position) - 5 (how many rows client sees above) + 3 (hidden) - 1 (0 baesd)
        = 5

        In this case then rows_before = [2, 5] and hidden = [3, 5] with total=12.

        The first island has rows_before[0](2) displayed rows above, with hidden[0](3)
        being folded into it, while second iland has rows_before[1](5) display rows
        above with hidden[1](5) being folded into it.
        """

        # slot the row before, after or between the rows:
        # 0 1 [2 3 4 5] 6 7 [8 9 10] 11
        #
        # for display rows 0 and 1:
        # slot 0: no islands before
        #
        # for display row 2, 3 and 4:
        # slot 1: after or at the first island
        i = bisect_right(self.rows_before, row) - 1
        if i < 0:
            # no run starts at or before this row - nothing hidden above
            return row
        if self.rows_before[i] == row:
            # run i itself
            # at 2 it's display row 2 as well as rows_before[0] == 2
            # it's own members are hidden below it, so only runs before count
            #
            # for 2: i = 0, so there is no previous run
            # for 5:
            # slot = 2
            # i = slot - 1 = 1
            # 5 + hidden[0](3) = 8
            # that corresponds to the start of the second isle in the example
            return row + (self.hidden[i - 1] if i else 0)

        # most of the cases it hits here, ads all hidden rows up until this point
        # for 6:
        # slot = 2
        # i = slot - 1 = 1
        # return 6 + hidden[1](5) = 11
        return row + self.hidden[i]


def build_layout(
    db: DbSession, conditions: list[Any], sort: str, order: str | None
) -> Layout:
    """Build the layout for one view in a single round trip.

    The SQL is one SELECT that returns one row:
        - run starts,
        - run sizes,
        - view's total
        - checkpoint ids.

    It walks the ordered view once with window functions. The caller is expected
    to have set work_mem and disabled parallel workers for it.
    """

    # Moment of the snapshot.
    # Filtering the on started_at <= as_of; session arriving after this pass is
    # is invisible to every page served.
    as_of = datetime.now(timezone.utc)
    stmt, keys = ordered_window(conditions, sort, order, as_of)

    # which session tried to log in; single row per session
    authed = select(AuthAttempt.session_id).distinct().subquery()

    # Attaching the story hash. It matches identical sessions.
    k = (
        # adding it to selects
        stmt.add_columns(story(authed.c.session_id.is_not(None), as_of).label("story"))
        # joining the SshClient for the story hash generation
        .outerjoin(SshClient, SshClient.session_id == Session.id)
        # joining the unique session log in attempts to the main sid
        .outerjoin(authed, authed.c.session_id == Session.id)
        .subquery("k")
    )

    # k is already ordered; this is a regular list, something like this:
    # [desc(k.c.o0), desc(k.c.o1)]
    # window functions need enforcing the row sequence snapshot is operating on
    window_row_order = order_clauses([k.c[f"o{i}"] for i in range(len(keys))], keys)

    # window pass:
    # one row per session, in order enforced by window_row_order rules
    b = select(
        # numbering the rows, 0 based (-1); `pos` is the snapshot position
        (func.row_number().over(order_by=window_row_order) - 1).label("pos"),
        # size of the whole result set; if we have 12 items - 12 in each row
        func.count().over().label("total"),
        # compare each session story
        k.c.story.is_distinct_from(
            # with it's predecessor
            func.lag(k.c.story).over(order_by=window_row_order)
            # `brk` is true when streak breaks and a different hash starts
        ).label("brk"),
        # carried along the operation, so that checkpoint reader may pick the id
        # at given positions - say at 0, 1000, 2000, ...
        k.c.sid,
        # defining this query as common table expression, since it will be read again
        # in case referenced more than once it's output is written as a temporary result,
        # so readers don't cause recomputing
    ).cte("b")

    # Stage isl: the islands. Keeping only the break rows and measuring each to
    # the next break gives every maximal stretch of equal stories with its start
    # and size. The last island has no next break and runs to `total`.
    isl = (
        select(
            # start of the island (first session into which 'see more' will be folded into)
            b.c.pos,
            # size of the entire result - for the final query
            b.c.total,
            (
                func.coalesce(
                    # lead corresponds to the *next* row in the window order;
                    # this query is constrained by `brk` true, so next record
                    # is the next island's start - first position that no longer
                    # blongs to previous island
                    func.lead(b.c.pos).over(order_by=b.c.pos),
                    # for the last island there is no next island, lead is null
                    # in such case; total means that the last island ends where
                    # the list ends
                    b.c.total,
                )
                # substracting the start of the current island from the start of the
                # returns its size
                - b.c.pos
            ).label("size"),
        )
        # keeps only the recirds for which the story changed
        # it is the first session into which 'see more' will be folded
        .where(b.c.brk)
        .subquery("isl")
    )
    # Only islands long enough to fold are runs. Most islands are singletons,
    # so filtering here keeps the layout proportional to the runs, not the rows.

    # fold only the islands that are larger or equal to RUN_MIN
    will_fold = isl.c.size >= RUN_MIN

    # Checkpoint ids, read straight from the window pass. ORDER BY pos is what
    # makes the array index meaningful: the i-th id is the session at position
    # i * _CHECKPOINT_EVERY.

    # checkpoint ids - read from the window pass
    checkpoints = (
        select(
            # collapse those multiples into one Postgres array of session ids,
            # in a position order
            func.array_agg(
                b.c.sid,
                # this ensures element order
                order_by=b.c.pos,
            )
        )
        # rows only being multiples of _CHECKPOINT_EVERY
        .where(b.c.pos % _CHECKPOINT_EVERY == 0)
        # select returns a single value - array of sids in order for each checkpoint
        .scalar_subquery()
    )

    # a single row is returned:
    # starts - array of positions where islands start
    # sizes - size of each island
    # total - all rows
    # checkpoint_ids - exact session ids, positions of which are i * _CHECKPOINT_EVERY
    starts, sizes, total, checkpoint_ids = db.execute(
        select(
            # gather the starting point of each island, filters for foldable ones
            func.array_agg(isl.c.pos).filter(will_fold),
            # gather the size of each island, while filters for foldable ones
            func.array_agg(isl.c.size).filter(will_fold),
            # the same value for each row, every ouput must be aggregate
            func.max(isl.c.total),
            # array of checkpoint of ids
            checkpoints,
        )
        # ensuring only one row is returned
    ).one()

    # two arrays pair up by index, but array_agg without order by doesn't ensure order
    # sorting pairs by the start, ensures snapshot order for the bisect
    runs = sorted(zip(starts or [], sizes or [], strict=True))

    # hidden count - a run of n shows one row and hides n - 1
    hidden = list(accumulate(n - 1 for _, n in runs))

    # display row is it's snapshot position, minus the sessions hidden by the runs prior
    # hidden[i] includes this run's own n - 1 ->
    #   sessions hidden before it are hidden[i] - (n - 1)
    # pos - (hidden[i] - (n - 1)) = pos - hidden[i] + n - 1
    #
    # example:
    # 0 1 [2 3 4 5] 6 7 [8 9 10] 11
    # where [x, y] contain hidden items
    #
    # runs = [(2, 4), (8, 3)]
    # hidden = [3, 5]
    #
    # For the first one:
    # when at 2 - all that users sees above 2 are 2 rows (none hidden)
    # 2 - 3 + 4 - 1 = 2
    #
    # For the second:
    # when at 8 - users see 5 rows with 2 hiding 3 more
    # 8 - 5 + 3 - 1 = 5
    rows_before = [pos - h + n - 1 for (pos, n), h in zip(runs, hidden, strict=True)]

    return Layout(
        as_of=as_of,  # snapshot moment
        total=total or 0,  # sessions in the snapshot
        rows_before=rows_before,  # visual display row, excluding hidden items
        hidden=hidden,  # sessions hidden within this series
        built_at=time.monotonic(),  # for cache's TTL
        # snapshot position, session_id
        checkpoints=[
            (i * _CHECKPOINT_EVERY, sid) for i, sid in enumerate(checkpoint_ids or [])
        ],
    )
