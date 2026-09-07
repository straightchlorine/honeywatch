"""Outcome facet counts for the Sessions page's Outcome filter panel."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from src.models.geo_location import GeoLocation
from src.models.session import Session
from src.services.types import OutcomeCountsDict


def outcome_counts(db: DbSession, country: str | None = None) -> OutcomeCountsDict:
    """Count sessions per outcome bucket with intentional overlap, scoped only by
    country so the panel does not shrink when toggled."""
    stmt = (
        select(
            func.count().filter(Session.auth_success.is_(True)).label("shell"),
            func.count().filter(Session.n_commands > 0).label("commands"),
            func.count().filter(Session.n_tcpip > 0).label("tcpip"),
            func.count().filter(Session.n_downloads > 0).label("downloads"),
            func.count().filter(Session.interest == 0).label("none"),
            func.count().label("total"),
        )
        .select_from(Session)
        .outerjoin(GeoLocation, GeoLocation.ip == Session.src_ip)
    )
    if country:
        stmt = stmt.where(GeoLocation.country_code == country)
    row = db.execute(stmt).one()
    return {
        "shell": row.shell,
        "commands": row.commands,
        "tcpip": row.tcpip,
        "downloads": row.downloads,
        "none": row.none,
        "total": row.total,
    }
