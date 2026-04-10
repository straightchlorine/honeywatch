from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.auth_attempt import AuthAttempt
from src.models.session import Session


def get_sessions_paginated(db: DbSession, page: int, per_page: int) -> dict[str, Any]:
    offset = (page - 1) * per_page

    count_stmt = select(func.count()).select_from(Session)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        select(Session)
        .options(selectinload(Session.auth_attempts))
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    sessions = list(db.execute(stmt).scalars().all())

    return {
        "sessions": [
            {
                "id": s.id,
                "src_ip": s.src_ip,
                "src_port": s.src_port,
                "dst_port": s.dst_port,
                "protocol": s.protocol,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "auth_attempt_count": len(s.auth_attempts),
            }
            for s in sessions
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


def get_session_detail(db: DbSession, session_id: str) -> dict[str, Any] | None:
    stmt = (
        select(Session)
        .options(
            selectinload(Session.auth_attempts),
            selectinload(Session.commands),
            selectinload(Session.downloads),
        )
        .where(Session.id == session_id)
    )
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return None

    return {
        "id": session.id,
        "src_ip": session.src_ip,
        "src_port": session.src_port,
        "dst_ip": session.dst_ip,
        "dst_port": session.dst_port,
        "protocol": session.protocol,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "sensor": session.sensor,
        "auth_attempts": [
            {
                "id": a.id,
                "username": a.username,
                "password": a.password,
                "success": a.success,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in session.auth_attempts
        ],
        "commands": [
            {
                "id": c.id,
                "input": c.input,
                "success": c.success,
                "timestamp": c.timestamp.isoformat() if c.timestamp else None,
            }
            for c in session.commands
        ],
        "downloads": [
            {
                "id": d.id,
                "url": d.url,
                "outfile": d.outfile,
                "sha256": d.sha256,
                "timestamp": d.timestamp.isoformat() if d.timestamp else None,
            }
            for d in session.downloads
        ],
    }


def get_stats(db: DbSession) -> dict[str, Any]:
    total_sessions = db.execute(select(func.count()).select_from(Session)).scalar_one()

    total_auth_attempts = db.execute(
        select(func.count()).select_from(AuthAttempt)
    ).scalar_one()

    unique_ips = db.execute(
        select(func.count(func.distinct(Session.src_ip)))
    ).scalar_one()

    top_usernames_rows = db.execute(
        select(AuthAttempt.username, func.count().label("count"))
        .group_by(AuthAttempt.username)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    top_usernames = [
        {"username": row[0], "count": row[1]} for row in top_usernames_rows
    ]

    top_passwords_rows = db.execute(
        select(AuthAttempt.password, func.count().label("count"))
        .group_by(AuthAttempt.password)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    top_passwords = [
        {"password": row[0], "count": row[1]} for row in top_passwords_rows
    ]

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    attacks_per_day_rows = db.execute(
        select(
            func.date(Session.started_at).label("day"),
            func.count().label("count"),
        )
        .where(Session.started_at >= thirty_days_ago)
        .group_by(func.date(Session.started_at))
        .order_by(func.date(Session.started_at))
    ).all()
    attacks_per_day = [
        {"date": str(row[0]), "count": row[1]} for row in attacks_per_day_rows
    ]

    return {
        "total_sessions": total_sessions,
        "total_auth_attempts": total_auth_attempts,
        "unique_ips": unique_ips,
        "top_usernames": top_usernames,
        "top_passwords": top_passwords,
        "attacks_per_day": attacks_per_day,
    }
