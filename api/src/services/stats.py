from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session as DbSession

from src.models.auth_attempt import AuthAttempt
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.types import (
    ActivityBucketDict,
    AuthOutcomesDict,
    CharsetClassDict,
    CredentialLengthDict,
    HeatmapPointDict,
    PasswordCompositionDict,
    TopCountryDict,
    TopCredentialDict,
    TopPasswordDict,
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

# Credential leaderboard knobs (the Credentials page). `by` chooses the grouping
# granularity, `metric` the ranking signal, `outcome` the cowrie accept/reject
# filter. Kept as frozensets so the marshmallow query schema and the service
# share one source of truth for the allowed values.
VALID_CRED_GROUPINGS = frozenset({"pair", "username", "password"})
VALID_CRED_METRICS = frozenset({"attempts", "ip_fanout"})
VALID_CRED_OUTCOMES = frozenset({"any", "success", "failed"})

# Attacker passwords are short and weak; cap the length histogram so a single
# pathological multi-KB password can't stretch the x-axis. The top bucket is
# rendered as "{cap}+".
PASSWORD_LENGTH_CAP = 16


class StatsService:
    """Compute aggregate honeypot metrics from the sessions schema."""

    def __init__(self, db: DbSession, top_n: int = DEFAULT_TOP_N) -> None:
        self.db = db
        self.top_n = top_n

    @staticmethod
    def _scope_country(stmt: Select[Any], country: str | None) -> Select[Any]:
        """Inner-join geo and filter to one source country when ``country`` is set."""
        if country:
            return stmt.join(GeoLocation, GeoLocation.ip == Session.src_ip).where(
                GeoLocation.country_code == country
            )
        return stmt

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

    def activity(
        self, bucket: str, country: str | None = None
    ) -> list[ActivityBucketDict]:
        """Return session counts grouped by time bucket.

        Args:
            bucket: One of ``"hour"``, ``"day"``, ``"month"``.
            country: ISO 3166-1 alpha-2 code to scope to one source country,
                or None for all countries.

        Raises:
            ValueError: When ``bucket`` is not a recognized value.
        """
        if bucket not in VALID_BUCKETS:
            raise ValueError(f"bucket must be one of {sorted(VALID_BUCKETS)}")
        since = datetime.now(timezone.utc) - _BUCKET_WINDOWS[bucket]
        trunc = func.date_trunc(bucket, Session.started_at)
        stmt = select(trunc.label("bucket"), func.count().label("count")).select_from(
            Session
        )
        stmt = self._scope_country(stmt, country)
        stmt = stmt.where(Session.started_at >= since).group_by(trunc).order_by(trunc)
        rows = self.db.execute(stmt).all()
        return [{"bucket": row[0].isoformat(), "count": row[1]} for row in rows]

    def trend(self, period_days: int = 7, country: str | None = None) -> TrendDict:
        """Compare session count in the last ``period_days`` vs the prior window.

        ``pct_change`` is ``None`` when the previous window has zero sessions
        (avoids divide-by-zero); the frontend renders the absolute delta only.
        ``country`` scopes both windows to a single source country when set.
        """
        now = datetime.now(timezone.utc)
        cur_start = now - timedelta(days=period_days)
        prev_start = cur_start - timedelta(days=period_days)
        current = self.db.execute(
            self._scope_country(
                select(func.count()).select_from(Session), country
            ).where(Session.started_at >= cur_start)
        ).scalar_one()
        previous = self.db.execute(
            self._scope_country(select(func.count()).select_from(Session), country)
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
        """Return the three headline counters in a single DB round-trip.

        Each counter is a scalar subquery, so Postgres returns all three from
        one statement instead of three sequential COUNT round-trips.
        """
        row = self.db.execute(
            select(
                select(func.count())
                .select_from(Session)
                .scalar_subquery()
                .label("total_sessions"),
                select(func.count())
                .select_from(AuthAttempt)
                .scalar_subquery()
                .label("total_auth_attempts"),
                select(func.count(func.distinct(Session.src_ip)))
                .scalar_subquery()
                .label("unique_ips"),
            )
        ).one()
        return {
            "total_sessions": row.total_sessions,
            "total_auth_attempts": row.total_auth_attempts,
            "unique_ips": row.unique_ips,
        }

    def heatmap(self, country: str | None = None) -> list[HeatmapPointDict]:
        """Return session counts for every hour x weekday combination.

        Weekday follows Postgres ``date_part('dow', ...)``: 0=Sunday ... 6=Saturday.
        ``country`` scopes to a single source country when set.
        """
        hour_col = func.extract("hour", Session.started_at)
        dow_col = func.extract("dow", Session.started_at)
        stmt = select(
            hour_col.label("hour"),
            dow_col.label("weekday"),
            func.count().label("count"),
        ).select_from(Session)
        stmt = self._scope_country(stmt, country)
        stmt = stmt.group_by(hour_col, dow_col).order_by(dow_col, hour_col)
        rows = self.db.execute(stmt).all()
        return [{"hour": int(r[0]), "weekday": int(r[1]), "count": r[2]} for r in rows]

    def top_credentials(
        self,
        by: str = "pair",
        metric: str = "attempts",
        outcome: str = "any",
    ) -> list[TopCredentialDict]:
        """Return the top-N attempted credentials, ranked by ``metric``.

        Args:
            by: ``"pair"`` groups by username+password (the botnet-fingerprint
                view); ``"username"`` groups by username alone (password is then
                ``None``); ``"password"`` groups by password alone (username is
                then ``None`` -- the raw "most common passwords" view).
            metric: ``"attempts"`` ranks by raw try count; ``"ip_fanout"`` ranks
                by the number of *distinct source IPs* that tried the credential
                -- the discriminator between a distributed botnet sharing a
                hardcoded table and a single brute-forcer. ``distinct_ips`` is
                only computed (and non-null) for ``"ip_fanout"`` so the cheap
                attempts view avoids the sessions join.
            outcome: ``"any"`` / ``"success"`` / ``"failed"`` filters on what
                cowrie accepted (``success=success`` / ``failed``).

        Raises:
            ValueError: For an unrecognized ``by`` / ``metric`` / ``outcome``.
        """
        if by not in VALID_CRED_GROUPINGS:
            raise ValueError(f"by must be one of {sorted(VALID_CRED_GROUPINGS)}")
        if metric not in VALID_CRED_METRICS:
            raise ValueError(f"metric must be one of {sorted(VALID_CRED_METRICS)}")
        if outcome not in VALID_CRED_OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(VALID_CRED_OUTCOMES)}")

        if by == "password":
            group_cols = [AuthAttempt.password]
        elif by == "pair":
            group_cols = [AuthAttempt.username, AuthAttempt.password]
        else:  # "username"
            group_cols = [AuthAttempt.username]
        count_col = func.count().label("count")
        selected: list[Any] = [*group_cols, count_col]
        fanout_col = None
        if metric == "ip_fanout":
            fanout_col = func.count(func.distinct(Session.src_ip)).label("distinct_ips")
            selected.append(fanout_col)

        stmt = select(*selected).select_from(AuthAttempt)
        if metric == "ip_fanout":
            stmt = stmt.join(Session, Session.id == AuthAttempt.session_id)
        if outcome == "success":
            stmt = stmt.where(AuthAttempt.success.is_(True))
        elif outcome == "failed":
            stmt = stmt.where(AuthAttempt.success.is_(False))
        stmt = stmt.group_by(*group_cols)
        if fanout_col is not None:
            stmt = stmt.order_by(fanout_col.desc(), count_col.desc())
        else:
            stmt = stmt.order_by(count_col.desc())
        stmt = stmt.limit(self.top_n)

        out: list[TopCredentialDict] = []
        for row in self.db.execute(stmt).all():
            idx = 0
            username = None
            password = None
            if by == "password":
                password = row[idx]
                idx += 1
            else:
                username = row[idx]
                idx += 1
                if by == "pair":
                    password = row[idx]
                    idx += 1
            count = row[idx]
            idx += 1
            distinct_ips = row[idx] if metric == "ip_fanout" else None
            out.append(
                {
                    "username": username,
                    "password": password,
                    "count": count,
                    "distinct_ips": distinct_ips,
                }
            )
        return out

    def auth_outcomes(self) -> AuthOutcomesDict:
        """Return the accept/reject split across all auth attempts.

        ``success_rate`` is the accepted percentage, ``None`` when there are no
        attempts yet (avoids divide-by-zero; the frontend renders a dash).
        """
        row = self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(AuthAttempt.success.is_(True)).label("successful"),
                func.count(func.distinct(AuthAttempt.password)).label(
                    "unique_passwords"
                ),
                func.count(func.distinct(AuthAttempt.username)).label(
                    "unique_usernames"
                ),
            ).select_from(AuthAttempt)
        ).one()
        total = row.total
        successful = row.successful
        failed = total - successful
        success_rate = round(successful / total * 100, 2) if total else None
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "unique_passwords": row.unique_passwords,
            "unique_usernames": row.unique_usernames,
        }

    def password_composition(self) -> PasswordCompositionDict:
        """Return the length histogram + charset-class breakdown of passwords.

        Lengths are capped at :data:`PASSWORD_LENGTH_CAP` (the top bucket is the
        ">= cap" tail). Each password is bucketed into exactly one charset class
        by priority: empty -> has a symbol -> all digits -> all lowercase ->
        all uppercase -> otherwise mixed alphanumeric. The classification is done
        in SQL (Postgres regex ``~``) so no rows cross the process boundary.
        """
        password = AuthAttempt.password
        length_expr = func.least(func.char_length(password), PASSWORD_LENGTH_CAP).label(
            "length"
        )
        length_rows = self.db.execute(
            select(length_expr, func.count().label("count"))
            .group_by(length_expr)
            .order_by(length_expr)
        ).all()
        lengths: list[CredentialLengthDict] = [
            {"length": int(r[0]), "count": r[1]} for r in length_rows
        ]

        charset = case(
            (func.char_length(password) == 0, "empty"),
            (password.op("~")("[^A-Za-z0-9]"), "symbol"),
            (password.op("~")("^[0-9]+$"), "digits"),
            (password.op("~")("^[a-z]+$"), "lower"),
            (password.op("~")("^[A-Z]+$"), "upper"),
            else_="alnum",
        ).label("name")
        class_rows = self.db.execute(
            select(charset, func.count().label("count"))
            .group_by(charset)
            .order_by(func.count().desc())
        ).all()
        classes: list[CharsetClassDict] = [
            {"name": r[0], "count": r[1]} for r in class_rows
        ]
        total = sum(c["count"] for c in classes)
        return {
            "total": total,
            "capped_at": PASSWORD_LENGTH_CAP,
            "lengths": lengths,
            "classes": classes,
        }

    def passwords_by_length(self, length: int) -> list[TopPasswordDict]:
        """Return the top-N passwords of a given length (histogram drill-down).

        ``length >= PASSWORD_LENGTH_CAP`` matches the ">= cap" tail bucket so the
        capped top bar lists every long password, not only those exactly at the
        cap -- mirrors how :meth:`password_composition` buckets that bar.
        """
        length_col = func.char_length(AuthAttempt.password)
        predicate = (
            length_col >= length
            if length >= PASSWORD_LENGTH_CAP
            else length_col == length
        )
        rows = self.db.execute(
            select(AuthAttempt.password, func.count().label("count"))
            .where(predicate)
            .group_by(AuthAttempt.password)
            .order_by(func.count().desc())
            .limit(self.top_n)
        ).all()
        return [{"password": row[0], "count": row[1]} for row in rows]


# Thin functional wrappers so route handlers depend on this module (the actual
# owner of stats logic) rather than reaching through services.sessions.


def get_totals(db: DbSession) -> TotalsDict:
    """Return total session, auth-attempt and unique-IP counts."""
    return StatsService(db).totals()


def get_top_passwords(
    db: DbSession, top_n: int = DEFAULT_TOP_N
) -> list[TopPasswordDict]:
    """Return the top-N attempted passwords by count, descending."""
    return StatsService(db, top_n=top_n).top_passwords()


def get_top_countries(
    db: DbSession, top_n: int = DEFAULT_TOP_N
) -> list[TopCountryDict]:
    """Return the top-N attacking countries by session count, descending."""
    return StatsService(db, top_n=top_n).top_countries()


def get_activity(
    db: DbSession, bucket: str, country: str | None = None
) -> list[ActivityBucketDict]:
    """Return session counts grouped by the given time bucket.

    Raises:
        ValueError: For unsupported ``bucket`` values.
    """
    return StatsService(db).activity(bucket, country)


def get_trend(
    db: DbSession, period_days: int = 7, country: str | None = None
) -> TrendDict:
    """Return the session-count trend over the last ``period_days``."""
    return StatsService(db).trend(period_days, country)


def get_heatmap(db: DbSession, country: str | None = None) -> list[HeatmapPointDict]:
    """Return session counts per (weekday, hour) cell."""
    return StatsService(db).heatmap(country)


def get_top_credentials(
    db: DbSession,
    by: str = "pair",
    metric: str = "attempts",
    outcome: str = "any",
    top_n: int = DEFAULT_TOP_N,
) -> list[TopCredentialDict]:
    """Return the top-N attempted credentials ranked by the chosen metric.

    Raises:
        ValueError: For unsupported ``by`` / ``metric`` / ``outcome`` values.
    """
    return StatsService(db, top_n=top_n).top_credentials(by, metric, outcome)


def get_auth_outcomes(db: DbSession) -> AuthOutcomesDict:
    """Return the accept/reject split across all auth attempts."""
    return StatsService(db).auth_outcomes()


def get_password_composition(db: DbSession) -> PasswordCompositionDict:
    """Return the password length histogram + charset-class breakdown."""
    return StatsService(db).password_composition()


def get_passwords_by_length(
    db: DbSession, length: int, top_n: int = DEFAULT_TOP_N
) -> list[TopPasswordDict]:
    """Return the top-N passwords whose length matches ``length``."""
    return StatsService(db, top_n=top_n).passwords_by_length(length)
