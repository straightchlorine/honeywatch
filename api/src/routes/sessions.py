from typing import Any

from flask import Blueprint, jsonify, request

from src.auth import require_auth
from src.extensions import SessionLocal
from src.services.sessions import get_session_detail, get_sessions_paginated, get_stats

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/sessions")
@require_auth
def list_sessions() -> tuple[Any, int]:
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    with SessionLocal() as db:
        result = get_sessions_paginated(db, page, per_page)
    return jsonify(result), 200


@api_bp.route("/sessions/<session_id>")
@require_auth
def session_detail(session_id: str) -> tuple[Any, int]:
    with SessionLocal() as db:
        result = get_session_detail(db, session_id)
    if result is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(result), 200


@api_bp.route("/stats")
@require_auth
def stats() -> tuple[Any, int]:
    with SessionLocal() as db:
        result = get_stats(db)
    return jsonify(result), 200
