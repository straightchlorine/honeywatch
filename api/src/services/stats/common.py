"""Pieces shared by more than one stats module."""

from __future__ import annotations

from typing import Any, Collection

from sqlalchemy import ColumnElement, Select

from src.models.geo_location import GeoLocation
from src.models.session import Session

DEFAULT_TOP_N = 10


def require_one_of(value: str, valid: Collection[str], name: str) -> None:
    """Raise ValueError if value is not in valid set."""
    if value not in valid:
        raise ValueError(f"{name} must be one of {sorted(valid)}")


# Country code standing in for sessions whose source IP has no geo_locations row.
UNKNOWN_COUNTRY = "??"


def country_match(country: str) -> ColumnElement[bool]:
    """SQL predicate for a single country on a geo_locations row."""
    if country == UNKNOWN_COUNTRY:
        return GeoLocation.country_code.is_(None)
    return GeoLocation.country_code == country


def scope_to_country(stmt: Select[Any], country: str | None) -> Select[Any]:
    """Join geo_locations and filter to a single country; None returns stmt
    unchanged."""
    if country is None:
        return stmt
    join = stmt.outerjoin if country == UNKNOWN_COUNTRY else stmt.join
    return join(GeoLocation, GeoLocation.ip == Session.src_ip).where(
        country_match(country)
    )
