import re
from typing import Any

from flask import Blueprint, jsonify, request

from src.extensions import get_session_factory
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

api_bp = Blueprint("api", __name__, url_prefix="/api")

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
def list_sessions() -> tuple[Any, int]:
    """Return a paginated list of sessions.

    Returns:
        Tuple of JSON body and HTTP status. Invalid ``page`` / ``per_page``
        values fall back to defaults; both are clamped to configured maxima.
    """
    page = _clamp_query_int("page", 1, 1, MAX_PAGE)
    per_page = _clamp_query_int("per_page", 20, 1, MAX_PER_PAGE)
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_sessions_paginated(db, page, per_page)
    return jsonify(result), 200


@api_bp.route("/sessions/<session_id>")
def session_detail(session_id: str) -> tuple[Any, int]:
    """Return full detail for a single session.

    Args:
        session_id: Cowrie session identifier; must match
            :data:`SESSION_ID_PATTERN` (alphanumeric, 1-32 chars).

    Returns:
        Tuple of JSON body and HTTP status. ``400`` on malformed id,
        ``404`` on unknown id.
    """
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return jsonify({"error": "Invalid session id"}), 400
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_session_detail(db, session_id)
    if result is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(result), 200


@api_bp.route("/stats/totals")
def stats_totals() -> tuple[Any, int]:
    """Return the headline totals (sessions, auth attempts, unique IPs)."""
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_totals(db)
    return jsonify(result), 200


@api_bp.route("/stats/top-passwords")
def stats_top_passwords() -> tuple[Any, int]:
    """Return the top-N attempted passwords ranked by count."""
    top_n = _clamp_query_int("top_n", 10, 1, MAX_TOP_N)
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_top_passwords(db, top_n)
    return jsonify(result), 200


@api_bp.route("/stats/top-countries")
def stats_top_countries() -> tuple[Any, int]:
    """Return the top-N attacking countries ranked by session count.

    Empty until the geolocation enricher (PR-B) populates ``geo_locations``.
    """
    top_n = _clamp_query_int("top_n", 10, 1, MAX_TOP_N)
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_top_countries(db, top_n)
    return jsonify(result), 200


@api_bp.route("/stats/activity")
def stats_activity() -> tuple[Any, int]:
    """Return session counts grouped by ``bucket`` (``hour|day|month``)."""
    bucket = request.args.get("bucket", "day")
    if bucket not in VALID_BUCKETS:
        return jsonify({"error": f"bucket must be one of {list(VALID_BUCKETS)}"}), 400
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_activity(db, bucket)
    return jsonify(result), 200


@api_bp.route("/stats/trend")
def stats_trend() -> tuple[Any, int]:
    """Return the session-count trend over ``period_days`` vs the prior window."""
    period_days = _clamp_query_int("period_days", 7, 1, MAX_PERIOD_DAYS)
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_trend(db, period_days)
    return jsonify(result), 200


@api_bp.route("/stats/heatmap")
def stats_heatmap() -> tuple[Any, int]:
    """Return session counts per (weekday, hour) cell."""
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_heatmap(db)
    return jsonify(result), 200
