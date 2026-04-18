from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.session import Session
from src.services.types import (
    AttacksPerDayDict,
    StatsDict,
    TopPasswordDict,
    TopUsernameDict,
)

DEFAULT_TOP_N = 10
DEFAULT_DAYS = 30


class StatsService:
    """Compute aggregate honeypot metrics from the sessions schema."""

    def __init__(
        self,
        db: DbSession,
        top_n: int = DEFAULT_TOP_N,
        days: int = DEFAULT_DAYS,
    ) -> None:
        self.db = db
        self.top_n = top_n
        self.days = days

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

    def attacks_per_day(self) -> list[AttacksPerDayDict]:
        """Return session counts per day over the last ``self.days`` days."""
        since = datetime.now(timezone.utc) - timedelta(days=self.days)
        rows = self.db.execute(
            select(
                func.date(Session.started_at).label("day"),
                func.count().label("count"),
            )
            .where(Session.started_at >= since)
            .group_by(func.date(Session.started_at))
            .order_by(func.date(Session.started_at))
        ).all()
        return [{"date": str(row[0]), "count": row[1]} for row in rows]

    def snapshot(self) -> StatsDict:
        """Aggregate every metric into the ``GET /api/stats`` response.

        Returns:
            A :class:`StatsDict` with totals, uniques, top-N auth data and
            the daily attack histogram.
        """
        return {
            "total_sessions": self.total_sessions(),
            "total_auth_attempts": self.total_auth_attempts(),
            "unique_ips": self.unique_ips(),
            "top_usernames": self.top_usernames(),
            "top_passwords": self.top_passwords(),
            "attacks_per_day": self.attacks_per_day(),
        }
