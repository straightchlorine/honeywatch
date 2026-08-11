"""Convert Session ORM rows to API response dicts.

No IP address is ever emitted: src_ip exists on the model only to join
geo_locations. Datetimes stay native here - the marshmallow response schemas
do the ISO formatting.
"""

from __future__ import annotations

from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.categories import classify_category
from src.services.redact import redact_ips
from src.services.types import (
    AuthAttemptDict,
    CommandDict,
    DownloadDict,
    SessionBaseDict,
    SessionDetailDict,
    SessionSummaryDict,
)


def _base(s: Session, geo: GeoLocation | None) -> SessionBaseDict:
    return {
        "id": s.id,
        "src_port": s.src_port,
        "dst_port": s.dst_port,
        "protocol": s.protocol,
        "country_code": geo.country_code if geo else None,
        "country": geo.country if geo else None,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
    }


def session_summary(
    s: Session,
    geo: GeoLocation | None,
    *,
    command_count: int,
    auth_attempt_count: int,
    login_success: bool,
) -> SessionSummaryDict:
    """Build a list-row summary.

    The counters are passed in because get_sessions_paginated aggregates
    them in SQL; reading them off the ORM relationships would load every
    command and auth attempt on the page.
    """
    return {
        **_base(s, geo),
        "auth_attempt_count": auth_attempt_count,
        "command_count": command_count,
        "has_successful_login": login_success,
        "category": classify_category(command_count, login_success, auth_attempt_count),
    }


def session_detail(s: Session, geo: GeoLocation | None) -> SessionDetailDict:
    return {
        **_base(s, geo),
        "sensor": s.sensor or None,
        "auth_attempts": [_dump_auth_attempt(a) for a in s.auth_attempts],
        "commands": [_dump_command(c) for c in s.commands],
        "downloads": [_dump_download(d) for d in s.downloads],
    }


def _dump_auth_attempt(a: AuthAttempt) -> AuthAttemptDict:
    return {
        "id": a.id,
        "username": a.username,
        "password": a.password,
        "success": a.success,
        "timestamp": a.timestamp,
    }


def _dump_command(c: Command) -> CommandDict:
    return {
        "id": c.id,
        "input": redact_ips(c.input) or "",
        "success": c.success,
        "timestamp": c.timestamp,
    }


def _dump_download(d: Download) -> DownloadDict:
    return {
        "id": d.id,
        "url": redact_ips(d.url),
        "outfile": d.outfile,
        "sha256": d.sha256,
        "timestamp": d.timestamp,
    }
