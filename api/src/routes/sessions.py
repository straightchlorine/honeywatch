from __future__ import annotations

from datetime import datetime
from typing import Any

from flask_smorest import Blueprint, abort

from src.extensions import get_session_factory
from src.schemas.sessions import (
    SessionDetailResponse,
    SessionIdPath,
    SessionsListQuery,
    SessionsListResponse,
)
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
    get_session_detail,
    get_sessions_paginated,
    get_top_countries,
    get_top_passwords,
    get_totals,
    get_trend,
)

sessions_bp = Blueprint(
    "sessions",
    "sessions",
    url_prefix="/api/v1/sessions",
    description="Honeypot session queries",
)
stats_bp = Blueprint(
    "stats",
    "stats",
    url_prefix="/api/v1/stats",
    description="Aggregate honeypot statistics",
)

_DATETIME_KEYS = ("started_at", "ended_at", "timestamp")


def _parse_dt(value: Any) -> Any:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _normalize_datetimes(payload: dict[str, Any]) -> dict[str, Any]:
    for key in _DATETIME_KEYS:
        if key in payload:
            payload[key] = _parse_dt(payload[key])
    for child_key in ("auth_attempts", "commands", "downloads"):
        children = payload.get(child_key)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    _normalize_datetimes(child)
    return payload


@sessions_bp.route("/")
@sessions_bp.doc(operationId="listSessions")
@sessions_bp.arguments(SessionsListQuery, location="query")
@sessions_bp.response(200, SessionsListResponse)
@sessions_bp.alt_response(422, "UnprocessableEntity")
def list_sessions(query_args: dict[str, Any]) -> dict[str, Any]:
    """Return a paginated list of session summaries."""
    page = query_args["page"]
    per_page = query_args["per_page"]
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_sessions_paginated(db, page, per_page)
    items = [_normalize_datetimes(dict(row)) for row in result["sessions"]]
    return {
        "items": items,
        "meta": {
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "total": result["total"],
        },
    }


@sessions_bp.route("/<session_id>")
@sessions_bp.doc(operationId="getSessionById")
@sessions_bp.arguments(SessionIdPath, location="view_args")
@sessions_bp.response(200, SessionDetailResponse)
@sessions_bp.alt_response(404, "NotFound")
@sessions_bp.alt_response(422, "UnprocessableEntity")
def session_detail(path_args: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Return full detail for a single session."""
    del path_args
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_session_detail(db, session_id)
    if result is None:
        abort(404, message=f"Session {session_id} not found")
    return _normalize_datetimes(dict(result))


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
