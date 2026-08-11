"""How much traffic arrived and when (Overview and Activity pages)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.session import Session
from src.services.stats.common import require_one_of, scope_to_country
from src.services.types import (
    ActivityBucketDict,
    HeatmapPointDict,
    TotalsDict,
    TrendDict,
)

VALID_BUCKETS = frozenset({"hour", "day", "month"})

# Roughly a screenful of bars at each resolution.
_BUCKET_WINDOWS = {
    "hour": timedelta(hours=24),
    "day": timedelta(days=30),
    "month": timedelta(days=365),
}


def totals(db: DbSession) -> TotalsDict:
    """The three headline counters, in one round trip."""
    # Loose index scan for the distinct src_ip count: walk the
    # sessions(src_ip) index one value at a time instead of aggregating
    # every row.
    skip = (
        select(Session.src_ip)
        .order_by(Session.src_ip)
        .limit(1)
        .cte("skip", recursive=True)
    )
    next_ip = (
        select(Session.src_ip)
        .where(Session.src_ip > skip.c.src_ip)
        .order_by(Session.src_ip)
        .limit(1)
        .scalar_subquery()
    )
    skip = skip.union_all(select(next_ip).where(skip.c.src_ip.isnot(None)))
    row = db.execute(
        select(
            select(func.count())
            .select_from(Session)
            .scalar_subquery()
            .label("total_sessions"),
            select(func.count())
            .select_from(AuthAttempt)
            .scalar_subquery()
            .label("total_auth_attempts"),
            select(func.count(skip.c.src_ip)).scalar_subquery().label("unique_ips"),
        )
    ).one()
    return {
        "total_sessions": row.total_sessions,
        "total_auth_attempts": row.total_auth_attempts,
        "unique_ips": row.unique_ips,
    }


def activity(
    db: DbSession, bucket: str, country: str | None = None
) -> list[ActivityBucketDict]:
    """Session counts per time bucket, oldest first.

    Only a trailing window is returned, sized to the bucket: 24h for "hour",
    30d for "day", 365d for "month". Empty buckets are absent.
    `bucket` must be in VALID_BUCKETS; anything else raises ValueError.
    """
    require_one_of(bucket, VALID_BUCKETS, "bucket")
    since = datetime.now(timezone.utc) - _BUCKET_WINDOWS[bucket]
    trunc = func.date_trunc(bucket, Session.started_at)
    stmt = select(trunc.label("bucket"), func.count().label("count")).select_from(
        Session
    )
    stmt = scope_to_country(stmt, country)
    stmt = stmt.where(Session.started_at >= since).group_by(trunc).order_by(trunc)
    rows = db.execute(stmt).all()
    return [{"bucket": row[0].isoformat(), "count": row[1]} for row in rows]


def trend(db: DbSession, period_days: int = 7, country: str | None = None) -> TrendDict:
    """Session count over the last `period_days` vs the window before it.

    `pct_change` is None when the previous window is empty (no baseline to
    divide by) - callers should fall back to `delta`.
    """
    now = datetime.now(timezone.utc)
    cur_start = now - timedelta(days=period_days)
    prev_start = cur_start - timedelta(days=period_days)
    current = db.execute(
        scope_to_country(select(func.count()).select_from(Session), country).where(
            Session.started_at >= cur_start
        )
    ).scalar_one()
    previous = db.execute(
        scope_to_country(select(func.count()).select_from(Session), country)
        .where(Session.started_at >= prev_start)
        .where(Session.started_at < cur_start)
    ).scalar_one()
    delta = current - previous
    pct_change = round(delta / previous * 100, 2) if previous else None
    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "pct_change": pct_change,
    }


def heatmap(db: DbSession, country: str | None = None) -> list[HeatmapPointDict]:
    """Session counts per (weekday, hour) cell, UTC.

    Weekday follows Postgres dow: 0=Sunday ... 6=Saturday. Cells with no
    sessions are absent from the result.
    """
    hour_col = func.extract("hour", Session.started_at)
    dow_col = func.extract("dow", Session.started_at)
    stmt = select(
        hour_col.label("hour"),
        dow_col.label("weekday"),
        func.count().label("count"),
    ).select_from(Session)
    stmt = scope_to_country(stmt, country)
    stmt = stmt.group_by(hour_col, dow_col).order_by(dow_col, hour_col)
    rows = db.execute(stmt).all()
    return [{"hour": int(r[0]), "weekday": int(r[1]), "count": r[2]} for r in rows]
