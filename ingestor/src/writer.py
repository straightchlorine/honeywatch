"""Persist cowrie events to PostgreSQL, with defensive isolation and truncation."""

from __future__ import annotations

import ipaddress
import logging
from types import TracebackType
from typing import Self

import psycopg
from psycopg_pool import ConnectionPool

from src import metrics
from src.events import (
    ClientFingerprint,
    ClientKex,
    ClientVersion,
    CommandInput,
    CowrieEvent,
    DirectTcpipRequest,
    FileDownload,
    LoginFailed,
    LoginSuccess,
    SessionClosed,
    SessionConnect,
)
from src.geoip import lookup as geoip_lookup
from src.sanitize import truncate

# Mirrors VARCHAR(N) in api/src/models/
_LEN_SESSION_ID = 64
_LEN_PROTOCOL = 16
_LEN_SENSOR = 64
_LEN_USERNAME = 256
_LEN_PASSWORD = 256
_LEN_COMMAND_INPUT = 8192
_LEN_URL = 2048
_LEN_OUTFILE = 512
_LEN_SHA256 = 64
_LEN_COUNTRY_CODE = 2
_LEN_COUNTRY = 128
_LEN_CITY = 128
_LEN_AS_ORG = 256
_LEN_CLIENT_VERSION = 256
_LEN_HASSH = 64
_LEN_HASSH_ALGORITHMS = 1024
_LEN_FINGERPRINT = 512
_LEN_FINGERPRINT_TYPE = 64
_LEN_HOST = 256
# kex/key/enc/mac/compression lists land in unbounded Text columns, but the
# attacker controls the pre-auth KEXINIT name-lists, so cap them defensively
# (hassh_algorithms is separately VARCHAR(1024)-capped via _LEN_HASSH_ALGORITHMS).
_LEN_ALGORITHMS = 4096

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

# Two events populate ssh_clients; each upserts only its own columns so it
# never clobbers the other's (version and kex arrive as separate events).
_UPSERT_SSH_CLIENT_VERSION = """
    INSERT INTO ssh_clients (session_id, client_version)
    VALUES (%(session_id)s, %(client_version)s)
    ON CONFLICT (session_id) DO UPDATE SET
        client_version = EXCLUDED.client_version
"""

_UPSERT_SSH_CLIENT_KEX = """
    INSERT INTO ssh_clients
        (session_id, hassh, hassh_algorithms, kex_algorithms,
         key_algorithms, encryption_algorithms, mac_algorithms,
         compression_algorithms)
    VALUES
        (%(session_id)s, %(hassh)s, %(hassh_algorithms)s, %(kex_algorithms)s,
         %(key_algorithms)s, %(encryption_algorithms)s, %(mac_algorithms)s,
         %(compression_algorithms)s)
    ON CONFLICT (session_id) DO UPDATE SET
        hassh                  = EXCLUDED.hassh,
        hassh_algorithms       = EXCLUDED.hassh_algorithms,
        kex_algorithms         = EXCLUDED.kex_algorithms,
        key_algorithms         = EXCLUDED.key_algorithms,
        encryption_algorithms  = EXCLUDED.encryption_algorithms,
        mac_algorithms         = EXCLUDED.mac_algorithms,
        compression_algorithms = EXCLUDED.compression_algorithms
"""

_INSERT_CLIENT_FINGERPRINT = """
    INSERT INTO client_fingerprints
        (session_id, username, fingerprint, fingerprint_type, timestamp)
    VALUES
        (%(session_id)s, %(username)s, %(fingerprint)s,
         %(fingerprint_type)s, %(timestamp)s)
"""

_INSERT_DIRECT_TCPIP = """
    INSERT INTO direct_tcpip_requests
        (session_id, dst_ip, dst_port, src_ip, src_port, timestamp)
    VALUES
        (%(session_id)s, %(dst_ip)s, %(dst_port)s,
         %(src_ip)s, %(src_port)s, %(timestamp)s)
"""


class EventWriter:
    """Persists the subset of cowrie events we care about to PostgreSQL.

    Events not matched below (e.g. `cowrie.client.size`, `cowrie.log.open`)
    are silently dropped - the raw line was already logged upstream so
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
            case ClientVersion():
                self._write_client_version(event)
            case ClientKex():
                self._write_client_kex(event)
            case ClientFingerprint():
                self._write_client_fingerprint(event)
            case DirectTcpipRequest():
                self._write_direct_tcpip(event)

    def _write_session_connect(self, event: SessionConnect) -> None:
        # Suppress cowrie's docker-compose healthcheck dials.
        # They must not contribute to the counts or pollute stats.
        if self._drop_loopback and _is_loopback(event.src_ip):
            return

        # Two transactions:
        # - session insert is durable;
        # - geo upsert is best-effort and never rolls back the session row
        with self.pool.connection() as conn:
            try:
                with conn.transaction():
                    conn.execute(
                        _INSERT_SESSION,
                        {
                            "id": truncate(event.session_id, _LEN_SESSION_ID),
                            "src_ip": event.src_ip,
                            "src_port": event.src_port,
                            "dst_ip": event.dst_ip,
                            "dst_port": event.dst_port,
                            "protocol": truncate(event.protocol, _LEN_PROTOCOL),
                            "started_at": event.timestamp,
                            "sensor": truncate(event.sensor, _LEN_SENSOR),
                        },
                    )
            except psycopg.errors.DataError as exc:
                self._drop_bad_event("session_connect", event.session_id, exc)
                return

            try:
                geo = geoip_lookup(event.src_ip)
            except Exception:
                # geoip.lookup is documented as never-raise, but isolate from
                # session-write outcome defensively.
                logger.warning(
                    "geoip lookup raised for %s; continuing without enrichment",
                    event.src_ip,
                    exc_info=True,
                )
                geo = None
            if geo is None:
                return
            try:
                with conn.transaction():
                    conn.execute(
                        _UPSERT_GEO,
                        {
                            "ip": event.src_ip,
                            "country_code": truncate(
                                geo.country_code, _LEN_COUNTRY_CODE
                            ),
                            "country": truncate(geo.country, _LEN_COUNTRY),
                            "city": truncate(geo.city, _LEN_CITY),
                            "latitude": geo.latitude,
                            "longitude": geo.longitude,
                            "asn": geo.asn,
                            "as_org": truncate(geo.as_org, _LEN_AS_ORG),
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
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "username": truncate(event.username, _LEN_USERNAME),
                        "password": truncate(event.password, _LEN_PASSWORD),
                        "success": isinstance(event, LoginSuccess),
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("auth", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("auth", event.session_id, exc)

    def _write_command(self, event: CommandInput) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_COMMAND,
                    {
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "input": truncate(event.input, _LEN_COMMAND_INPUT),
                        "success": True,
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("cmd", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("cmd", event.session_id, exc)

    def _write_download(self, event: FileDownload) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_DOWNLOAD,
                    {
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "url": truncate(event.url, _LEN_URL),
                        "outfile": truncate(event.outfile, _LEN_OUTFILE),
                        "sha256": truncate(event.sha256, _LEN_SHA256),
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("download", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("download", event.session_id, exc)

    def _write_session_closed(self, event: SessionClosed) -> None:
        with self.pool.connection() as conn:
            try:
                cur = conn.execute(
                    _UPDATE_SESSION_CLOSED,
                    {
                        "id": truncate(event.session_id, _LEN_SESSION_ID),
                        "ended_at": event.timestamp,
                    },
                )
            except psycopg.errors.DataError as exc:
                self._drop_bad_event("session_closed", event.session_id, exc)
                return
            if cur.rowcount == 0:
                self._log_orphan("session_closed", event.session_id)

    def _write_client_version(self, event: ClientVersion) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _UPSERT_SSH_CLIENT_VERSION,
                    {
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "client_version": truncate(event.version, _LEN_CLIENT_VERSION),
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("client_version", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("client_version", event.session_id, exc)

    def _write_client_kex(self, event: ClientKex) -> None:
        def _join(values: list[str]) -> str | None:
            return truncate(",".join(values), _LEN_ALGORITHMS) if values else None

        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _UPSERT_SSH_CLIENT_KEX,
                    {
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "hassh": truncate(event.hassh, _LEN_HASSH),
                        "hassh_algorithms": truncate(
                            event.hasshAlgorithms, _LEN_HASSH_ALGORITHMS
                        ),
                        "kex_algorithms": _join(event.kexAlgs),
                        "key_algorithms": _join(event.keyAlgs),
                        "encryption_algorithms": _join(event.encCS),
                        "mac_algorithms": _join(event.macCS),
                        "compression_algorithms": _join(event.compCS),
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("client_kex", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("client_kex", event.session_id, exc)

    def _write_client_fingerprint(self, event: ClientFingerprint) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_CLIENT_FINGERPRINT,
                    {
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "username": truncate(event.username, _LEN_USERNAME),
                        "fingerprint": truncate(event.fingerprint, _LEN_FINGERPRINT),
                        "fingerprint_type": truncate(event.type, _LEN_FINGERPRINT_TYPE),
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("client_fingerprint", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("client_fingerprint", event.session_id, exc)

    def _write_direct_tcpip(self, event: DirectTcpipRequest) -> None:
        try:
            with self.pool.connection() as conn:
                conn.execute(
                    _INSERT_DIRECT_TCPIP,
                    {
                        "session_id": truncate(event.session_id, _LEN_SESSION_ID),
                        "dst_ip": truncate(event.dst_ip, _LEN_HOST),
                        "dst_port": event.dst_port,
                        "src_ip": truncate(event.src_ip, _LEN_HOST),
                        "src_port": event.src_port,
                        "timestamp": event.timestamp,
                    },
                )
        except psycopg.errors.ForeignKeyViolation:
            self._log_orphan("direct_tcpip", event.session_id)
        except psycopg.errors.DataError as exc:
            self._drop_bad_event("direct_tcpip", event.session_id, exc)

    @staticmethod
    def _log_orphan(kind: str, session_id: str) -> None:
        """Log + meter an event whose session row never landed.

        Happens at startup mid-stream (ingestor restart with tail seeking to
        EOF, connect event missed) or under sustained DB outages where the
        connect itself failed.
        """
        metrics.orphan_event_total.labels(kind=kind).inc()
        logger.info("orphan %s event for session_id=%s", kind, session_id)

    @staticmethod
    def _drop_bad_event(kind: str, session_id: str, exc: psycopg.Error) -> None:
        """Skip a row Postgres rejected as malformed (NUL byte, encoding, etc).

        Without this, the writer's retry/fuse keeps replaying the same
        poison event forever, blocking the queue.

        Logs the SQLSTATE only - never `exc_info`: the DataError message
        echoes the rejected attacker value verbatim, which would smuggle
        unsanitized bytes (ANSI/CRLF log forgery) into the operator's log sink.
        """
        metrics.events_dropped_total.labels(reason="db_data_error").inc()
        logger.warning(
            "dropping malformed %s event for session_id=%s sqlstate=%s",
            kind,
            session_id,
            getattr(exc, "sqlstate", "-"),
        )
