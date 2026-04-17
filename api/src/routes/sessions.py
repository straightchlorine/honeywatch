from typing import Any

from flask import Blueprint, jsonify, request

# Import the module, not the name: `init_db` rebinds extensions.SessionLocal
# at app startup, so we must look up the current factory at call time rather
# than capturing the module-load sqlite stub via `from ... import SessionLocal`.
from src import extensions
from src.services.sessions import get_session_detail, get_sessions_paginated, get_stats

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_PER_PAGE = 100
MAX_PAGE = 10_000


@api_bp.route("/sessions")
def list_sessions() -> tuple[Any, int]:
    page = max(1, min(request.args.get("page", 1, type=int), MAX_PAGE))
    per_page = max(1, min(request.args.get("per_page", 20, type=int), MAX_PER_PAGE))
    with extensions.SessionLocal() as db:
        result = get_sessions_paginated(db, page, per_page)
    return jsonify(result), 200


@api_bp.route("/sessions/<session_id>")
def session_detail(session_id: str) -> tuple[Any, int]:
    with extensions.SessionLocal() as db:
        result = get_session_detail(db, session_id)
    if result is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(result), 200


@api_bp.route("/stats")
def stats() -> tuple[Any, int]:
    with extensions.SessionLocal() as db:
        result = get_stats(db)
    return jsonify(result), 200
