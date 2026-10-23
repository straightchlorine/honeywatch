"""Turning a page of ordered rows into display rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Row

from src.services.sessions.common import RUN_MIN
from src.services.types import RunDict


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


def fold(rows: Sequence[Row[Any]], offset: int) -> list[tuple[str, RunDict | None]]:
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
