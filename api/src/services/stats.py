from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.types import (
    ActivityBucketDict,
    HeatmapPointDict,
    TopCountryDict,
    TopPasswordDict,
    TopUsernameDict,
    TotalsDict,
    TrendDict,
)

DEFAULT_TOP_N = 10
VALID_BUCKETS = frozenset({"hour", "day", "month"})
_BUCKET_WINDOWS = {
    "hour": timedelta(hours=24),
    "day": timedelta(days=30),
    "month": timedelta(days=365),
}


class StatsService:
    """Compute aggregate honeypot metrics from the sessions schema."""

    def __init__(self, db: DbSession, top_n: int = DEFAULT_TOP_N) -> None:
        self.db = db
        self.top_n = top_n

    def total_sessions(self) -> int:
        """Return the total number of recorded sessions."""
        return self.db.execute(select(func.count()).select_from(Session)).scalar_one()

    def total_auth_attempts(self) -> int:
        """Return the total number of recorded authentication attempts."""
        return self.db.execute(
            select(func.count()).select_from(AuthAttempt)
        ).scalar_one()

    def unique_ips(self) -> int:
        """Return the number of distinct source IPs observed in sessions."""
        return self.db.execute(
            select(func.count(func.distinct(Session.src_ip)))
        ).scalar_one()

    def top_usernames(self) -> list[TopUsernameDict]:
        """Return the top-N attempted usernames by count, descending."""
        rows = self.db.execute(
            select(AuthAttempt.username, func.count().label("count"))
            .group_by(AuthAttempt.username)
            .order_by(func.count().desc())
            .limit(self.top_n)
        ).all()
        return [{"username": row[0], "count": row[1]} for row in rows]

    def top_passwords(self) -> list[TopPasswordDict]:
        """Return the top-N attempted passwords by count, descending."""
        rows = self.db.execute(
            select(AuthAttempt.password, func.count().label("count"))
            .group_by(AuthAttempt.password)
            .order_by(func.count().desc())
            .limit(self.top_n)
        ).all()
        return [{"password": row[0], "count": row[1]} for row in rows]

    def top_countries(self) -> list[TopCountryDict]:
        """Return the top-N attacking countries by session count, descending.

        Sessions whose `src_ip` has no `geo_locations` row (geo enrichment
        pending or failed -- the ingestor splits session vs geo writes for
        availability) are bucketed under "Unknown" rather than dropped.
        """
        country_code = func.coalesce(GeoLocation.country_code, "??").label(
            "country_code"
        )
        country = func.coalesce(GeoLocation.country, "Unknown").label("country")
        rows = self.db.execute(
            select(
                country_code,
                country,
                func.count(Session.id).label("count"),
            )
            .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
            .group_by(country_code, country)
            .order_by(func.count(Session.id).desc())
            .limit(self.top_n)
        ).all()
        return [{"country_code": r[0], "country": r[1], "count": r[2]} for r in rows]

    def activity(self, bucket: str) -> list[ActivityBucketDict]:
        """Return session counts grouped by time bucket.

        Args:
            bucket: One of ``"hour"``, ``"day"``, ``"month"``.

        Raises:
            ValueError: When ``bucket`` is not a recognized value.
        """
        if bucket not in VALID_BUCKETS:
            raise ValueError(f"bucket must be one of {sorted(VALID_BUCKETS)}")
        since = datetime.now(timezone.utc) - _BUCKET_WINDOWS[bucket]
        trunc = func.date_trunc(bucket, Session.started_at)
        rows = self.db.execute(
            select(trunc.label("bucket"), func.count().label("count"))
            .where(Session.started_at >= since)
            .group_by(trunc)
            .order_by(trunc)
        ).all()
        return [{"bucket": row[0].isoformat(), "count": row[1]} for row in rows]

    def trend(self, period_days: int = 7) -> TrendDict:
        """Compare session count in the last ``period_days`` vs the prior window.

        ``pct_change`` is ``None`` when the previous window has zero sessions
        (avoids divide-by-zero); the frontend renders the absolute delta only.
        """
        now = datetime.now(timezone.utc)
        cur_start = now - timedelta(days=period_days)
        prev_start = cur_start - timedelta(days=period_days)
        current = self.db.execute(
            select(func.count())
            .select_from(Session)
            .where(Session.started_at >= cur_start)
        ).scalar_one()
        previous = self.db.execute(
            select(func.count())
            .select_from(Session)
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

    def totals(self) -> TotalsDict:
        """Return the three headline counters in a single roll-up."""
        return {
            "total_sessions": self.total_sessions(),
            "total_auth_attempts": self.total_auth_attempts(),
            "unique_ips": self.unique_ips(),
        }

    def heatmap(self) -> list[HeatmapPointDict]:
        """Return session counts for every hour x weekday combination.

        Weekday follows Postgres ``date_part('dow', ...)``: 0=Sunday ... 6=Saturday.
        """
        hour_col = func.extract("hour", Session.started_at)
        dow_col = func.extract("dow", Session.started_at)
        rows = self.db.execute(
            select(
                hour_col.label("hour"),
                dow_col.label("weekday"),
                func.count().label("count"),
            )
            .group_by(hour_col, dow_col)
            .order_by(dow_col, hour_col)
        ).all()
        return [{"hour": int(r[0]), "weekday": int(r[1]), "count": r[2]} for r in rows]
