import re
from typing import Any

from flask import Blueprint, jsonify, request

from src.extensions import get_session_factory
from src.services.sessions import get_session_detail, get_sessions_paginated, get_stats

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_PER_PAGE = 100
MAX_PAGE = 10_000
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


@api_bp.route("/stats")
def stats() -> tuple[Any, int]:
    """Return aggregate honeypot stats.

    Returns:
        Tuple of JSON body and HTTP status; see
        :class:`src.services.stats.StatsService` for the shape.
    """
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_stats(db)
    return jsonify(result), 200
