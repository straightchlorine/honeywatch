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
    CountriesDict,
    CountryAsnDict,
    CountryRowDict,
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

# Country leaderboard ranking knobs (the Countries page). The sort picks which
# per-country aggregate ranks the list. Shared as a frozenset so the marshmallow
# query schema and the service agree on the allowed values.
VALID_COUNTRY_SORTS = frozenset({"sessions", "ips", "attempts", "success_rate"})

# Sentinel country code for the geo-less bucket (no resolved country_code).
UNKNOWN_COUNTRY = "??"

# Attacker passwords are short and weak; cap the length histogram so a single
# pathological multi-KB password can't stretch the x-axis.
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

    def country_breakdown(self, sort: str = "sessions") -> CountriesDict:
        """Return per-country attack metrics for the Countries leaderboard.

        One row per source country with both session-grain metrics (sessions,
        distinct source IPs) and auth-grain metrics (attempts, accepted,
        distinct usernames/passwords). Each grain is aggregated at its native
        level first (a session-grain subquery and an auth-grain subquery), then
        joined on the country code -- so the session/IP counts are never
        multiplied by a session's auth-attempt count (the fan-out a single
        mixed-grain join would cause). Geo-less sessions bucket under
        "Unknown"/"??" (outer join + COALESCE), same as :meth:`top_countries`.

        Args:
            sort: Ranking metric; one of :data:`VALID_COUNTRY_SORTS`.

        Raises:
            ValueError: When ``sort`` is not a recognized value.
        """
        if sort not in VALID_COUNTRY_SORTS:
            raise ValueError(f"sort must be one of {sorted(VALID_COUNTRY_SORTS)}")

        # Session grain: one row per session (no auth join), so the distinct
        # session/IP counts are exact. geo.ip is the PK -> the outer join is
        # 1:1; geo-less sessions COALESCE into the "??"/"Unknown" bucket.
        sess_cc = func.coalesce(GeoLocation.country_code, UNKNOWN_COUNTRY).label(
            "country_code"
        )
        sess_country = func.coalesce(GeoLocation.country, "Unknown").label("country")
        sess_agg = (
            select(
                sess_cc,
                sess_country,
                func.count(func.distinct(Session.id)).label("sessions"),
                func.count(func.distinct(Session.src_ip)).label("distinct_ips"),
            )
            .select_from(Session)
            .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
            .group_by(sess_cc, sess_country)
            .subquery()
        )

        # Auth grain: one row per auth attempt. Every attempt's session is in
        # sess_agg under the same country, so these metrics LEFT JOIN back onto
        # the session-grain rows.
        auth_cc = func.coalesce(GeoLocation.country_code, UNKNOWN_COUNTRY).label(
            "country_code"
        )
        auth_agg = (
            select(
                auth_cc,
                func.count(AuthAttempt.id).label("attempts"),
                func.count(AuthAttempt.id)
                .filter(AuthAttempt.success.is_(True))
                .label("successful"),
                func.count(func.distinct(AuthAttempt.username)).label(
                    "distinct_usernames"
                ),
                func.count(func.distinct(AuthAttempt.password)).label(
                    "distinct_passwords"
                ),
            )
            .select_from(AuthAttempt)
            .join(Session, Session.id == AuthAttempt.session_id)
            .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
            .group_by(auth_cc)
            .subquery()
        )

        sessions = sess_agg.c.sessions
        distinct_ips = sess_agg.c.distinct_ips
        attempts = func.coalesce(auth_agg.c.attempts, 0).label("attempts")
        successful = func.coalesce(auth_agg.c.successful, 0).label("successful")
        # COALESCE null (no-attempt country) to -1 so it sorts last under DESC
        # without a separate NULLS LAST clause.
        rate_order = func.coalesce(
            auth_agg.c.successful * 1.0 / func.nullif(auth_agg.c.attempts, 0),
            -1.0,
        )
        order_by = {
            "sessions": sessions.desc(),
            "ips": distinct_ips.desc(),
            "attempts": attempts.desc(),
            "success_rate": rate_order.desc(),
        }[sort]

        rows = self.db.execute(
            select(
                sess_agg.c.country_code,
                sess_agg.c.country,
                sessions,
                distinct_ips,
                attempts,
                successful,
                func.coalesce(auth_agg.c.distinct_usernames, 0).label(
                    "distinct_usernames"
                ),
                func.coalesce(auth_agg.c.distinct_passwords, 0).label(
                    "distinct_passwords"
                ),
            )
            .select_from(sess_agg)
            .outerjoin(auth_agg, auth_agg.c.country_code == sess_agg.c.country_code)
            # Stable tiebreak on sessions keeps equal-rank rows deterministic.
            .order_by(order_by, sessions.desc())
            .limit(self.top_n)
        ).all()

        countries: list[CountryRowDict] = []
        for r in rows:
            att = r.attempts
            countries.append(
                {
                    "country_code": r.country_code,
                    "country": r.country,
                    "sessions": r.sessions,
                    "distinct_ips": r.distinct_ips,
                    "attempts": att,
                    "successful": r.successful,
                    "success_rate": round(r.successful / att * 100, 2) if att else None,
                    "distinct_usernames": r.distinct_usernames,
                    "distinct_passwords": r.distinct_passwords,
                }
            )

        # Header counters in one scan of Session <-> GeoLocation (one round-trip):
        # total/resolved session counts for the coverage pct, plus the distinct
        # resolved-country count. geo.ip is the PK so the outer join is 1:1 (no
        # session fan-out); COUNT(DISTINCT country_code) ignores the null bucket.
        header = self.db.execute(
            select(
                func.count().label("total"),
                func.count()
                .filter(GeoLocation.country_code.isnot(None))
                .label("resolved"),
                func.count(func.distinct(GeoLocation.country_code)).label(
                    "total_countries"
                ),
            )
            .select_from(Session)
            .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
        ).one()
        geo_resolved_pct = (
            round(header.resolved / header.total * 100, 2) if header.total else None
        )
        return {
            "countries": countries,
            "total_countries": header.total_countries,
            "geo_resolved_pct": geo_resolved_pct,
        }

    def country_asns(self, country: str | None = None) -> list[CountryAsnDict]:
        """Return the top-N source networks (ASN / org) by session count.

        Surfaces which hosting/cloud networks the attacks ride. ``country``
        scopes to one origin (the Countries detail panel always passes one);
        ``"??"`` scopes to the geo-less bucket (sessions with no resolved country
        that still carry an ASN -- the MaxMind ASN-hit-without-city case); None
        returns the global top networks. Rows without an ``asn`` are excluded.
        Reports counts only -- no source addresses cross the boundary.
        """
        sessions = func.count(func.distinct(Session.id)).label("sessions")
        distinct_ips = func.count(func.distinct(Session.src_ip)).label("distinct_ips")
        stmt = (
            select(GeoLocation.asn, GeoLocation.as_org, sessions, distinct_ips)
            .select_from(Session)
            .join(GeoLocation, GeoLocation.ip == Session.src_ip)
            .where(GeoLocation.asn.isnot(None))
        )
        if country == UNKNOWN_COUNTRY:
            stmt = stmt.where(GeoLocation.country_code.is_(None))
        elif country is not None:
            stmt = stmt.where(GeoLocation.country_code == country)
        rows = self.db.execute(
            stmt.group_by(GeoLocation.asn, GeoLocation.as_org)
            .order_by(sessions.desc())
            .limit(self.top_n)
        ).all()
        return [
            {
                "asn": r.asn,
                "as_org": r.as_org,
                "sessions": r.sessions,
                "distinct_ips": r.distinct_ips,
            }
            for r in rows
        ]

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
        country: str | None = None,
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
            country: ISO 3166-1 alpha-2 code to scope to one source country --
                the per-country credential dictionary (top passwords/usernames
                from that origin), or None for all countries.

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
        # Reach Session once for either the fan-out distinct-IP count or the
        # country geo join (both need AuthAttempt -> Session);
        if metric == "ip_fanout" or country is not None:
            stmt = stmt.join(Session, Session.id == AuthAttempt.session_id)
        if country == UNKNOWN_COUNTRY:
            # The geo-less bucket: scope to sessions whose src_ip has no resolved
            # country (outer join keeps null-geo rows that an inner join drops).
            stmt = stmt.outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip).where(
                GeoLocation.country_code.is_(None)
            )
        elif country is not None:
            stmt = stmt.join(GeoLocation, GeoLocation.ip == Session.src_ip).where(
                GeoLocation.country_code == country
            )
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
