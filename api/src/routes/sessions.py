import re
from typing import Any

from flask import abort, jsonify, request
from flask_smorest import Blueprint

from src.extensions import get_session_factory
from src.schemas.sessions import SessionDetailSchema, SessionsListSchema
from src.schemas.stats import (
    ActivityBucketSchema,
    HeatmapPointSchema,
    TopCountrySchema,
    TopPasswordSchema,
    TotalsSchema,
    TrendSchema,
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

api_bp = Blueprint(
    "api", "api", url_prefix="/api", description="Honeywatch session + stats API"
)

MAX_PER_PAGE = 100
MAX_PAGE = 10_000
MAX_TOP_N = 100
MAX_PERIOD_DAYS = 365
VALID_BUCKETS = ("hour", "day", "month")
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,32}$")


def _clamp_query_int(name: str, default: int, lo: int, hi: int) -> int:
    """Read a positive integer query param and clamp it into ``[lo, hi]``.

    Args:
        name: Query parameter name.
        default: Value used when the param is missing or non-integer.
        lo: Inclusive lower bound.
        hi: Inclusive upper bound.

    Returns:
        The clamped integer.
    """
    raw = request.args.get(name, type=int)
    value = raw if raw is not None else default
    return max(lo, min(value, hi))


@api_bp.route("/sessions")
@api_bp.response(200, SessionsListSchema)
def list_sessions() -> dict[str, Any]:
    """Return a paginated list of sessions.

    Invalid ``page`` / ``per_page`` values fall back to defaults; both are
    clamped to configured maxima.
    """
    page = _clamp_query_int("page", 1, 1, MAX_PAGE)
    per_page = _clamp_query_int("per_page", 20, 1, MAX_PER_PAGE)
    session_factory = get_session_factory()
    with session_factory() as db:
        return dict(get_sessions_paginated(db, page, per_page))


@api_bp.route("/sessions/<session_id>")
@api_bp.response(200, SessionDetailSchema)
def session_detail(session_id: str) -> Any:
    """Return full detail for a single session.

    ``session_id`` must match alphanumeric, 1-32 chars; ``400`` on malformed
    id, ``404`` on unknown id.
    """
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return jsonify({"error": "Invalid session id"}), 400
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_session_detail(db, session_id)
    if result is None:
        abort(404, description="Session not found")
    return dict(result)


@api_bp.route("/stats/totals")
@api_bp.response(200, TotalsSchema)
def stats_totals() -> dict[str, Any]:
    """Return the headline totals (sessions, auth attempts, unique IPs)."""
    session_factory = get_session_factory()
    with session_factory() as db:
        return dict(get_totals(db))


@api_bp.route("/stats/top-passwords")
@api_bp.response(200, TopPasswordSchema(many=True))
def stats_top_passwords() -> list[dict[str, Any]]:
    """Return the top-N attempted passwords ranked by count."""
    top_n = _clamp_query_int("top_n", 10, 1, MAX_TOP_N)
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_top_passwords(db, top_n)]


@api_bp.route("/stats/top-countries")
@api_bp.response(200, TopCountrySchema(many=True))
def stats_top_countries() -> list[dict[str, Any]]:
    """Return the top-N attacking countries ranked by session count.

    Empty until the geolocation enricher populates ``geo_locations``.
    """
    top_n = _clamp_query_int("top_n", 10, 1, MAX_TOP_N)
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_top_countries(db, top_n)]


@api_bp.route("/stats/activity")
@api_bp.response(200, ActivityBucketSchema(many=True))
def stats_activity() -> Any:
    """Return session counts grouped by ``bucket`` (``hour|day|month``)."""
    bucket = request.args.get("bucket", "day")
    if bucket not in VALID_BUCKETS:
        return jsonify({"error": f"bucket must be one of {list(VALID_BUCKETS)}"}), 400
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_activity(db, bucket)]


@api_bp.route("/stats/trend")
@api_bp.response(200, TrendSchema)
def stats_trend() -> dict[str, Any]:
    """Return the session-count trend over ``period_days`` vs the prior window."""
    period_days = _clamp_query_int("period_days", 7, 1, MAX_PERIOD_DAYS)
    session_factory = get_session_factory()
    with session_factory() as db:
        return dict(get_trend(db, period_days))


@api_bp.route("/stats/heatmap")
@api_bp.response(200, HeatmapPointSchema(many=True))
def stats_heatmap() -> list[dict[str, Any]]:
    """Return session counts per (weekday, hour) cell."""
    session_factory = get_session_factory()
    with session_factory() as db:
        return [dict(row) for row in get_heatmap(db)]
