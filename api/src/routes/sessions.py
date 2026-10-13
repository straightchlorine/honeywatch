from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app
from flask_smorest import Blueprint, abort

from src.extensions import get_db
from src.schemas.sessions import (
    RunSessionsResponse,
    SessionDetailResponse,
    SessionIdPath,
    SessionRunQuery,
    SessionsListQuery,
    SessionsListResponse,
)
from src.services.sessions import (
    get_run_members,
    get_session_detail,
    get_sessions_folded,
    get_sessions_paginated,
)
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
    filters = _filters(query_args)
    page, per_page = query_args["page"], query_args["per_page"]
    if query_args["fold"]:
        folded = get_sessions_folded(get_db(), page, per_page, **filters)
        return {
            "items": folded["sessions"],
            "meta": _meta(folded),
            "max_interest": folded["max_interest"],
            "as_of": folded["as_of"],
        }
    result = get_sessions_paginated(get_db(), page, per_page, **filters)
    return {
        "items": result["sessions"],
        "meta": _meta(result),
        "max_interest": result["max_interest"],
    }


@sessions_bp.route("/run")
@sessions_bp.doc(operationId="listRunSessions")
@sessions_bp.arguments(SessionRunQuery, location="query")
@sessions_bp.response(200, RunSessionsResponse)
@sessions_bp.alt_response(422, "UnprocessableEntity")
@sessions_bp.alt_response(500, "InternalServerError")
def list_run_sessions(query_args: dict[str, Any]) -> dict[str, Any]:
    """Return a page of the sessions folded into one run of a folded list."""
    result = get_run_members(
        get_db(),
        query_args["page"],
        query_args["per_page"],
        as_of=query_args["as_of"],
        offset=query_args["offset"],
        count=query_args["count"],
        **_filters(query_args),
    )
    return {"items": result["sessions"], "meta": _meta(result)}


def _filters(query_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "q": query_args.get("q"),
        "country": query_args.get("country"),
        "category": query_args.get("category"),
        "sort": query_args.get("sort", "recent"),
        "order": query_args.get("order"),
        "has": query_args.get("has"),
        "sha256": query_args.get("sha256"),
    }


def _meta(result: Mapping[str, Any]) -> dict[str, Any]:
    return {k: result[k] for k in ("page", "per_page", "pages", "total")}


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
