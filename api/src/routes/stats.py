from __future__ import annotations

from typing import Any

from flask_smorest import Blueprint

from src.extensions import get_session_factory
from src.schemas.stats import (
    ActivityBucketResponse,
    ActivityQuery,
    HeatmapPointResponse,
    TopCountriesQuery,
    TopCountryResponse,
    TopPasswordResponse,
    TopPasswordsQuery,
    TotalsResponse,
    TrendQuery,
    TrendResponse,
)
from src.services.sessions import (
    get_activity,
    get_heatmap,
    get_top_countries,
    get_top_passwords,
    get_totals,
    get_trend,
)

stats_bp = Blueprint(
    "stats",
    "stats",
    url_prefix="/api/v1/stats",
    description="Aggregate honeypot statistics",
)


@stats_bp.route("/totals")
@stats_bp.doc(operationId="statsTotals")
@stats_bp.response(200, TotalsResponse)
def stats_totals() -> dict[str, Any]:
    """Return headline totals (sessions, auth attempts, unique IPs)."""
    session_factory = get_session_factory()
    with session_factory() as db:
        return dict(get_totals(db))


@stats_bp.route("/top-passwords")
@stats_bp.doc(operationId="statsTopPasswords")
@stats_bp.arguments(TopPasswordsQuery, location="query")
@stats_bp.response(200, TopPasswordResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
def stats_top_passwords(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the top-N attempted passwords ranked by count."""
    top_n = query_args["top_n"]
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_top_passwords(db, top_n)]


@stats_bp.route("/top-countries")
@stats_bp.doc(operationId="statsTopCountries")
@stats_bp.arguments(TopCountriesQuery, location="query")
@stats_bp.response(200, TopCountryResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
def stats_top_countries(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the top-N attacking countries ranked by session count."""
    top_n = query_args["top_n"]
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_top_countries(db, top_n)]


@stats_bp.route("/activity")
@stats_bp.doc(operationId="statsActivity")
@stats_bp.arguments(ActivityQuery, location="query")
@stats_bp.response(200, ActivityBucketResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
def stats_activity(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return session counts grouped by bucket (hour|day|month)."""
    bucket = query_args["bucket"]
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_activity(db, bucket)]


@stats_bp.route("/trend")
@stats_bp.doc(operationId="statsTrend")
@stats_bp.arguments(TrendQuery, location="query")
@stats_bp.response(200, TrendResponse)
@stats_bp.alt_response(422, "UnprocessableEntity")
def stats_trend(query_args: dict[str, Any]) -> dict[str, Any]:
    """Return the session-count trend over period_days vs the prior window."""
    period_days = query_args["period_days"]
    session_factory = get_session_factory()
    with session_factory() as db:
        return dict(get_trend(db, period_days))


@stats_bp.route("/heatmap")
@stats_bp.doc(operationId="statsHeatmap")
@stats_bp.response(200, HeatmapPointResponse(many=True))
def stats_heatmap() -> list[dict[str, Any]]:
    """Return session counts per (weekday, hour) cell."""
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_heatmap(db)]
