"""SSH client and fingerprint tracking for Origins page."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from src.models.client_fingerprint import ClientFingerprint
from src.models.session import Session
from src.models.ssh_client import SshClient
from src.services.redact import redact_ips
from src.services.stats.common import DEFAULT_TOP_N
from src.services.types import FingerprintDict, SshClientDict


def ssh_clients(db: DbSession, top_n: int = DEFAULT_TOP_N) -> list[SshClientDict]:
    """Top-N SSH client versions by session count (excludes NULL versions)."""
    stmt = (
        select(
            SshClient.client_version,
            func.count().label("sessions"),
        )
        .where(SshClient.client_version.isnot(None))
        .group_by(SshClient.client_version)
        .order_by(func.count().desc())
        .limit(top_n)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "client_version": redact_ips(r.client_version, numeric_hosts=False),
            "sessions": r.sessions,
        }
        for r in rows
    ]


def fingerprints(db: DbSession, top_n: int = DEFAULT_TOP_N) -> list[FingerprintDict]:
    """Top-N SSH client fingerprints by distinct session count, with IP/session
    counts and timestamps."""
    stmt = (
        select(
            ClientFingerprint.fingerprint,
            ClientFingerprint.fingerprint_type,
            func.count(func.distinct(ClientFingerprint.session_id)).label(
                "session_count"
            ),
            func.count(func.distinct(Session.src_ip)).label("distinct_ips"),
            func.min(ClientFingerprint.timestamp).label("first_seen"),
            func.max(ClientFingerprint.timestamp).label("last_seen"),
        )
        .join(Session, Session.id == ClientFingerprint.session_id)
        .group_by(ClientFingerprint.fingerprint, ClientFingerprint.fingerprint_type)
        .order_by(
            func.count(func.distinct(Session.src_ip)).desc(),
            func.count(func.distinct(ClientFingerprint.session_id)).desc(),
        )
        .limit(top_n)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "fingerprint": r.fingerprint,
            "fingerprint_type": r.fingerprint_type,
            "sessions": r.session_count,
            "ips": r.distinct_ips,
            "first_seen": r.first_seen.isoformat() if r.first_seen else None,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
        }
        for r in rows
    ]
