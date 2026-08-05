"""Pieces shared by more than one stats module."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Select

from src.models.geo_location import GeoLocation
from src.models.session import Session

DEFAULT_TOP_N = 10

# Country code standing in for sessions whose source IP has no geo_locations row.
UNKNOWN_COUNTRY = "??"


def country_match(country: str) -> ColumnElement[bool]:
    """Predicate selecting one country on an already-joined geo_locations row."""
    if country == UNKNOWN_COUNTRY:
        return GeoLocation.country_code.is_(None)
    return GeoLocation.country_code == country


def scope_to_country(stmt: Select[Any], country: str | None) -> Select[Any]:
    """Join geo_locations onto Session.src_ip and keep a single country.

    None leaves `stmt` alone. UNKNOWN_COUNTRY needs the outer join: the rows it
    asks for are exactly the ones with no geo_locations match.
    """
    if country is None:
        return stmt
    join = stmt.outerjoin if country == UNKNOWN_COUNTRY else stmt.join
    return join(GeoLocation, GeoLocation.ip == Session.src_ip).where(
        country_match(country)
    )
