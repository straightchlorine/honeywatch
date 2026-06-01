from __future__ import annotations

from typing import Any

from flask_smorest import Blueprint

from src.extensions import get_db
from src.schemas.stats import (
    ActivityBucketResponse,
    ActivityQuery,
    HeatmapPointResponse,
    HeatmapQuery,
    TopCountryResponse,
    TopNQuery,
    TopPasswordResponse,
    TotalsResponse,
    TrendQuery,
    TrendResponse,
)
from src.services.stats import (
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
@stats_bp.alt_response(500, "InternalServerError")
def stats_totals() -> dict[str, Any]:
    """Return headline totals (sessions, auth attempts, unique IPs)."""
    return dict(get_totals(get_db()))


@stats_bp.route("/top-passwords")
@stats_bp.doc(operationId="statsTopPasswords")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, TopPasswordResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_top_passwords(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the top-N attempted passwords ranked by count."""
    return [dict(row) for row in get_top_passwords(get_db(), query_args["top_n"])]


@stats_bp.route("/top-countries")
@stats_bp.doc(operationId="statsTopCountries")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, TopCountryResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_top_countries(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the top-N attacking countries ranked by session count."""
    return [dict(row) for row in get_top_countries(get_db(), query_args["top_n"])]


@stats_bp.route("/activity")
@stats_bp.doc(operationId="statsActivity")
@stats_bp.arguments(ActivityQuery, location="query")
@stats_bp.response(200, ActivityBucketResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_activity(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return session counts grouped by bucket (hour|day|month)."""
    return [
        dict(row)
        for row in get_activity(
            get_db(), query_args["bucket"], query_args.get("country")
        )
    ]


@stats_bp.route("/trend")
@stats_bp.doc(operationId="statsTrend")
@stats_bp.arguments(TrendQuery, location="query")
@stats_bp.response(200, TrendResponse)
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_trend(query_args: dict[str, Any]) -> dict[str, Any]:
    """Return the session-count trend over period_days vs the prior window."""
    return dict(
        get_trend(get_db(), query_args["period_days"], query_args.get("country"))
    )


@stats_bp.route("/heatmap")
@stats_bp.doc(operationId="statsHeatmap")
@stats_bp.arguments(HeatmapQuery, location="query")
@stats_bp.response(200, HeatmapPointResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_heatmap(query_args: dict[str, Any]) -> list[dict[str, Any]]:
    """Return session counts per (weekday, hour) cell."""
    return [dict(row) for row in get_heatmap(get_db(), query_args.get("country"))]
