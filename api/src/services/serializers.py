from __future__ import annotations

from datetime import datetime

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.types import (
    AuthAttemptDict,
    CommandDict,
    DownloadDict,
    SessionDetailDict,
    SessionSummaryDict,
)


def _iso(dt: datetime | None) -> str | None:
    """Return an ISO-8601 string or ``None`` for nullable datetime columns."""
    return dt.isoformat() if dt else None


class SessionSerializer:
    """Convert :class:`Session` ORM rows to API response dicts.

    ``src_ip`` is deliberately omitted from every external shape. The IP is
    retained on the DB column for internal joins (``geo_locations``) only.
    """

    @staticmethod
    def summary(s: Session, geo: GeoLocation | None) -> SessionSummaryDict:
        """Serialize a Session into the list-endpoint shape.

        Args:
            s: Session row with ``auth_attempts`` loaded.
            geo: Optional joined :class:`GeoLocation` for the session's source IP.
        """
        return {
            "id": s.id,
            "src_port": s.src_port,
            "dst_port": s.dst_port,
            "protocol": s.protocol,
            "country_code": geo.country_code if geo else None,
            "country": geo.country if geo else None,
            "started_at": _iso(s.started_at),
            "ended_at": _iso(s.ended_at),
            "auth_attempt_count": len(s.auth_attempts),
        }

    @staticmethod
    def detail(s: Session, geo: GeoLocation | None) -> SessionDetailDict:
        """Serialize a Session with its children into the detail shape.

        Args:
            s: Session row with ``auth_attempts``, ``commands`` and
                ``downloads`` loaded.
            geo: Optional joined :class:`GeoLocation` for the session's source IP.
        """
        return {
            "id": s.id,
            "src_port": s.src_port,
            "dst_ip": s.dst_ip,
            "dst_port": s.dst_port,
            "protocol": s.protocol,
            "country_code": geo.country_code if geo else None,
            "country": geo.country if geo else None,
            "started_at": _iso(s.started_at),
            "ended_at": _iso(s.ended_at),
            "sensor": s.sensor if s.sensor else None,
            "auth_attempts": [AuthAttemptSerializer.dump(a) for a in s.auth_attempts],
            "commands": [CommandSerializer.dump(c) for c in s.commands],
            "downloads": [DownloadSerializer.dump(d) for d in s.downloads],
        }


class AuthAttemptSerializer:
    """Convert :class:`AuthAttempt` ORM rows to API response dicts."""

    @staticmethod
    def dump(a: AuthAttempt) -> AuthAttemptDict:
        """Serialize a single auth attempt.

        Args:
            a: AuthAttempt row.

        Returns:
            The auth-attempt dict embedded in session detail responses.
        """
        return {
            "id": a.id,
            "username": a.username,
            "password": a.password,
            "success": a.success,
            "timestamp": _iso(a.timestamp),
        }


class CommandSerializer:
    """Convert :class:`Command` ORM rows to API response dicts."""

    @staticmethod
    def dump(c: Command) -> CommandDict:
        """Serialize a single command.

        Args:
            c: Command row.

        Returns:
            The command dict embedded in session detail responses.
        """
        return {
            "id": c.id,
            "input": c.input,
            "success": c.success,
            "timestamp": _iso(c.timestamp),
        }


class DownloadSerializer:
    """Convert :class:`Download` ORM rows to API response dicts."""

    @staticmethod
    def dump(d: Download) -> DownloadDict:
        """Serialize a single download.

        Args:
            d: Download row.

        Returns:
            The download dict embedded in session detail responses.
        """
        return {
            "id": d.id,
            "url": d.url,
            "outfile": d.outfile,
            "sha256": d.sha256,
            "timestamp": _iso(d.timestamp),
        }
