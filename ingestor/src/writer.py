from __future__ import annotations

import logging

from psycopg_pool import ConnectionPool

from src.parser import (
    CommandInput,
    CowrieEvent,
    FileDownload,
    LoginAttempt,
    SessionClosed,
    SessionConnect,
)

logger = logging.getLogger(__name__)

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
    INSERT INTO sessions (id, ended_at)
    VALUES (%(id)s, %(ended_at)s)
    ON CONFLICT (id) DO UPDATE SET ended_at = EXCLUDED.ended_at
"""

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


class EventWriter:
    """Writes parsed cowrie events to PostgreSQL using a connection pool."""

    def __init__(self, conninfo: str) -> None:
        self.pool = ConnectionPool(conninfo)

    def write_event(self, event: CowrieEvent) -> None:
        """Dispatch and write a single event to the database."""
        match event:
            case SessionConnect():
                self._write_session_connect(event)
            case LoginAttempt():
                self._write_login_attempt(event)
            case CommandInput():
                self._write_command(event)
            case FileDownload():
                self._write_download(event)
            case SessionClosed():
                self._write_session_closed(event)

    def _write_session_connect(self, event: SessionConnect) -> None:
        with self.pool.connection() as conn:
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

    def _write_login_attempt(self, event: LoginAttempt) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                _INSERT_AUTH_ATTEMPT,
                {
                    "session_id": event.session_id,
                    "username": event.username,
                    "password": event.password,
                    "success": event.success,
                    "timestamp": event.timestamp,
                },
            )

    def _write_command(self, event: CommandInput) -> None:
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

    def _write_download(self, event: FileDownload) -> None:
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

    def _write_session_closed(self, event: SessionClosed) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                _UPDATE_SESSION_CLOSED,
                {
                    "id": event.session_id,
                    "ended_at": event.timestamp,
                },
            )

    def close(self) -> None:
        """Close the connection pool."""
        self.pool.close()
