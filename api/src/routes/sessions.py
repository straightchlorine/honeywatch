from __future__ import annotations

from typing import Any

from flask import current_app, request
from flask_smorest import Blueprint, abort

from src.extensions import get_session_factory
from src.schemas.sessions import (
    SessionDetailResponse,
    SessionIdPath,
    SessionsListQuery,
    SessionsListResponse,
)
from src.services.sessions import get_session_detail, get_sessions_paginated

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
def list_sessions(query_args: dict[str, Any]) -> dict[str, Any]:
    """Return a paginated list of session summaries."""
    page = query_args["page"]
    per_page = query_args["per_page"]
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_sessions_paginated(db, page, per_page)
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
def session_detail(_path_args: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Return full detail for a single session."""
    session_factory = get_session_factory()
    with session_factory() as db:
        result = get_session_detail(db, session_id)
    if result is None:
        current_app.logger.info(
            "session not found id=%r remote=%s", session_id, request.remote_addr
        )
        abort(404, message="Session not found")
    return dict(result)  # type: ignore[arg-type]
