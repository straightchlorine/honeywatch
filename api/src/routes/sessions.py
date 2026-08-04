from __future__ import annotations

from typing import Any

from flask import current_app
from flask_smorest import Blueprint, abort

from src.extensions import get_db
from src.schemas.sessions import (
    SessionDetailResponse,
    SessionIdPath,
    SessionsListQuery,
    SessionsListResponse,
)
from src.services.sessions import get_session_detail, get_sessions_paginated
from src.services.types import SessionDetailDict

sessions_bp = Blueprint(
    "sessions",
    "sessions",
    url_prefix="/api/v1/sessions",
    description="Honeypot session queries",
)


@sessions_bp.route("/")
@sessions_bp.doc(operationId="listSessions")
@sessions_bp.arguments(SessionsListQuery, location="query")
@sessions_bp.response(200, SessionsListResponse)
@sessions_bp.alt_response(422, "UnprocessableEntity")
@sessions_bp.alt_response(500, "InternalServerError")
def list_sessions(query_args: dict[str, Any]) -> dict[str, Any]:
    """Return a paginated list of session summaries."""
    result = get_sessions_paginated(
        get_db(),
        query_args["page"],
        query_args["per_page"],
        country=query_args.get("country"),
        category=query_args.get("category"),
        sort=query_args.get("sort", "recent"),
    )
    return {
        "items": result["sessions"],
        "meta": {
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "total": result["total"],
        },
    }


@sessions_bp.route("/<session_id>")
@sessions_bp.doc(operationId="getSessionById")
@sessions_bp.arguments(SessionIdPath, location="path")
@sessions_bp.response(200, SessionDetailResponse)
@sessions_bp.alt_response(404, "NotFound")
@sessions_bp.alt_response(422, "UnprocessableEntity")
@sessions_bp.alt_response(500, "InternalServerError")
def session_detail(_path_args: dict[str, Any], session_id: str) -> SessionDetailDict:
    """Return full detail for a single session."""
    result = get_session_detail(get_db(), session_id)
    if result is None:
        current_app.logger.info("session not found id=%r", session_id)
        abort(404, message="Session not found")
    return result
