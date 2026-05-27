from __future__ import annotations

import ipaddress
import logging
from types import TracebackType
from typing import Self

import psycopg
from psycopg_pool import ConnectionPool

from src import metrics
from src.events import (
    CommandInput,
    CowrieEvent,
    FileDownload,
    LoginFailed,
    LoginSuccess,
    SessionClosed,
    SessionConnect,
)
from src.geoip import lookup as geoip_lookup

logger = logging.getLogger(__name__)


def _is_loopback(src_ip: str | None) -> bool:
    """Return True if `src_ip` parses as a loopback IP address.

    Args:
        src_ip: IP string or None.

    Returns:
        True for loopback addresses; False for None, empty, or unparseable input.
    """
    if not src_ip:
        return False
    try:
        return ipaddress.ip_address(src_ip).is_loopback
    except ValueError:
        return False


_INSERT_SESSION = """
    INSERT INTO sessions
        (id, src_ip, src_port, dst_ip, dst_port,
         protocol, started_at, sensor)
    VALUES
        (%(id)s, %(src_ip)s, %(src_port)s, %(dst_ip)s,
         %(dst_port)s, %(protocol)s, %(started_at)s, %(sensor)s)
    ON CONFLICT (id) DO NOTHING
"""

_UPDATE_SESSION_CLOSED = """
    UPDATE sessions SET ended_at = %(ended_at)s WHERE id = %(id)s
"""
# Pure UPDATE, no upsert. Rationale: postgres validates the INSERT row
# (including NOT NULL constraints on src_ip/src_port) before evaluating
# ON CONFLICT, so an upsert with partial columns blows up.
# If no connect event this session, silently skip the close - no half-empty rows.

_INSERT_AUTH_ATTEMPT = """
    INSERT INTO auth_attempts (session_id, username, password, success, timestamp)
    VALUES (%(session_id)s, %(username)s, %(password)s, %(success)s, %(timestamp)s)
"""

_INSERT_COMMAND = """
    INSERT INTO commands (session_id, input, success, timestamp)
    VALUES (%(session_id)s, %(input)s, %(success)s, %(timestamp)s)
"""

_INSERT_DOWNLOAD = """
    INSERT INTO downloads (session_id, url, outfile, sha256, timestamp)
    VALUES (%(session_id)s, %(url)s, %(outfile)s, %(sha256)s, %(timestamp)s)
"""

_UPSERT_GEO = """
    INSERT INTO geo_locations
        (ip, country_code, country, city, latitude, longitude,
         asn, as_org, last_updated)
    VALUES
        (%(ip)s, %(country_code)s, %(country)s, %(city)s, %(latitude)s,
         %(longitude)s, %(asn)s, %(as_org)s, now())
    ON CONFLICT (ip) DO UPDATE SET
        country_code = EXCLUDED.country_code,
        country      = EXCLUDED.country,
        city         = EXCLUDED.city,
        latitude     = EXCLUDED.latitude,
        longitude    = EXCLUDED.longitude,
        asn          = EXCLUDED.asn,
        as_org       = EXCLUDED.as_org,
        last_updated = now()
"""


class EventWriter:
    """Persists the subset of cowrie events we care about to PostgreSQL.

    Events not matched below (e.g. `cowrie.client.kex`, `cowrie.log.open`)
    are silently dropped -- the raw line was already logged upstream so
    nothing is lost from an observability standpoint.
    """

    def __init__(self, conninfo: str, *, drop_loopback: bool = True) -> None:
        # `check=` runs on every checkout
        self.pool = ConnectionPool(
            conninfo, open=False, check=ConnectionPool.check_connection
        )
        self._drop_loopback = drop_loopback

    def __enter__(self) -> Self:
        self.pool.open()
        self.pool.wait()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.pool.close()

    def write_event(self, event: CowrieEvent) -> None:
        """Persist a cowrie event to PostgreSQL.

        Args:
            event: The parsed cowrie event.

        Note:
            Events not matched by the dispatch table are silently dropped.
        """
        match event:
            case SessionConnect():
                self._write_session_connect(event)
            case LoginSuccess() | LoginFailed():
                self._write_login_attempt(event)
            case CommandInput():
                self._write_command(event)
            case FileDownload():
                self._write_download(event)
            case SessionClosed():
                self._write_session_closed(event)

    def _write_session_connect(self, event: SessionConnect) -> None:
        # Suppress cowrie's docker-compose healthcheck dials.
        # They must not contribute to the counts or pollute stats.
        if self._drop_loopback and _is_loopback(event.src_ip):
            return

        # Two transactions:
        # - session insert is durable;
        # - geo upsert is best-effort and never rolls back the session row
        with self.pool.connection() as conn:
            with conn.transaction():
                conn.execute(
                    _INSERT_SESSION,
                    {
                        "id": event.session_id,
                        "src_ip": event.src_ip,
                        "src_port": event.src_port,
                        "dst_ip": event.dst_ip,
                        "dst_port": event.dst_port,
                        "protocol": event.protocol,
                        "started_at": event.timestamp,
                        "sensor": event.sensor,
                    },
                )

            geo = geoip_lookup(event.src_ip)
            if geo is None:
                return
            try:
                with conn.transaction():
                    conn.execute(
                        _UPSERT_GEO,
                        {
                            "ip": event.src_ip,
                            "country_code": geo.country_code,
                            "country": geo.country,
                            "city": geo.city,
                            "latitude": geo.latitude,
                            "longitude": geo.longitude,
                            "asn": geo.asn,
                            "as_org": geo.as_org,
                        },
                    )
            except psycopg.Error:
                metrics.geo_upsert_failures_total.inc()
                logger.warning(
                    "geo upsert failed for %s; session row preserved",
                    event.src_ip,
                    exc_info=True,
                )

    def _write_login_attempt(self, event: LoginSuccess | LoginFailed) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_AUTH_ATTEMPT,
                    {
                        "session_id": event.session_id,
                        "username": event.username,
                        "password": event.password,
                        "success": isinstance(event, LoginSuccess),
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("auth", event.session_id)

    def _write_command(self, event: CommandInput) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_COMMAND,
                    {
                        "session_id": event.session_id,
                        "input": event.input,
                        "success": True,
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("cmd", event.session_id)

    def _write_download(self, event: FileDownload) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_DOWNLOAD,
                    {
                        "session_id": event.session_id,
                        "url": event.url,
                        "outfile": event.outfile,
                        "sha256": event.sha256,
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("download", event.session_id)

    def _write_session_closed(self, event: SessionClosed) -> None:
        with self.pool.connection() as conn:
            cur = conn.execute(
                _UPDATE_SESSION_CLOSED,
                {
                    "id": event.session_id,
                    "ended_at": event.timestamp,
                },
            )
            if cur.rowcount == 0:
                self._log_orphan("session_closed", event.session_id)

    @staticmethod
    def _log_orphan(kind: str, session_id: str) -> None:
        """Log + meter an event whose session row never landed.

        Happens at startup mid-stream (ingestor restart with tail seeking to
        EOF, connect event missed) or under sustained DB outages where the
        connect itself failed.
        """
        metrics.orphan_event_total.labels(kind=kind).inc()
        logger.info("orphan %s event for session_id=%s", kind, session_id)
