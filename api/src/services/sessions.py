from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from src.models.session import Session
from src.services.serializers import SessionSerializer
from src.services.stats import StatsService
from src.services.types import SessionDetailDict, SessionsPageDict, StatsDict


def get_sessions_paginated(db: DbSession, page: int, per_page: int) -> SessionsPageDict:
    """Return a page of sessions ordered by most recent first.

    Args:
        db: Active SQLAlchemy session.
        page: 1-indexed page number.
        per_page: Page size; the caller is responsible for clamping.

    Returns:
        A :class:`SessionsPageDict` with the session summaries plus
        pagination metadata.
    """
    offset = (page - 1) * per_page

    total = db.execute(select(func.count()).select_from(Session)).scalar_one()

    stmt = (
        select(Session)
        .options(selectinload(Session.auth_attempts))
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    sessions = list(db.execute(stmt).scalars().all())

    return {
        "sessions": [SessionSerializer.summary(s) for s in sessions],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


def get_session_detail(db: DbSession, session_id: str) -> SessionDetailDict | None:
    """Return the full detail for a single session, or ``None`` if missing.

    Args:
        db: Active SQLAlchemy session.
        session_id: Cowrie session identifier.

    Returns:
        A :class:`SessionDetailDict` with auth attempts, commands and
        downloads, or ``None`` when no session matches.
    """
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
    return SessionSerializer.detail(session)


def get_stats(db: DbSession) -> StatsDict:
    """Return the aggregate stats snapshot for ``GET /api/stats``.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        The :class:`StatsDict` snapshot produced by :class:`StatsService`.
    """
    return StatsService(db).snapshot()
