from __future__ import annotations

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.categories import classify_category
from src.services.types import (
    AuthAttemptDict,
    CommandDict,
    DownloadDict,
    SessionDetailDict,
    SessionSummaryDict,
)


class SessionSerializer:
    """Convert :class:`Session` ORM rows to API response dicts.

    ``src_ip`` is deliberately omitted from every external shape. The IP is
    retained on the DB column for internal joins (``geo_locations``) only.

    Datetime fields are emitted as native ``datetime`` objects; the marshmallow
    response schemas format them with ``DateTime(format="iso")`` exactly once.
    """

    @staticmethod
    def summary(
        s: Session,
        geo: GeoLocation | None,
        *,
        command_count: int,
        auth_attempt_count: int,
        login_success: bool,
    ) -> SessionSummaryDict:
        """Build a list-row summary from a session plus precomputed counters.

        The per-session counters are aggregated in SQL by the list query (see
        :func:`src.services.sessions.get_sessions_paginated`) rather than by
        materializing the ``commands``/``auth_attempts`` collections, so they are
        passed in instead of read off the ORM relationships.
        """
        return {
            "id": s.id,
            "src_port": s.src_port,
            "dst_port": s.dst_port,
            "protocol": s.protocol,
            "country_code": geo.country_code if geo else None,
            "country": geo.country if geo else None,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "auth_attempt_count": auth_attempt_count,
            "command_count": command_count,
            "has_successful_login": login_success,
            "category": classify_category(
                command_count, login_success, auth_attempt_count
            ),
        }

    @staticmethod
    def detail(s: Session, geo: GeoLocation | None) -> SessionDetailDict:
        return {
            "id": s.id,
            "src_port": s.src_port,
            "dst_port": s.dst_port,
            "protocol": s.protocol,
            "country_code": geo.country_code if geo else None,
            "country": geo.country if geo else None,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "sensor": s.sensor if s.sensor else None,
            "auth_attempts": [AuthAttemptSerializer.dump(a) for a in s.auth_attempts],
            "commands": [CommandSerializer.dump(c) for c in s.commands],
            "downloads": [DownloadSerializer.dump(d) for d in s.downloads],
        }


class AuthAttemptSerializer:
    @staticmethod
    def dump(a: AuthAttempt) -> AuthAttemptDict:
        return {
            "id": a.id,
            "username": a.username,
            "password": a.password,
            "success": a.success,
            "timestamp": a.timestamp,
        }


class CommandSerializer:
    @staticmethod
    def dump(c: Command) -> CommandDict:
        return {
            "id": c.id,
            "input": c.input,
            "success": c.success,
            "timestamp": c.timestamp,
        }


class DownloadSerializer:
    @staticmethod
    def dump(d: Download) -> DownloadDict:
        return {
            "id": d.id,
            "url": d.url,
            "outfile": d.outfile,
            "sha256": d.sha256,
            "timestamp": d.timestamp,
        }
