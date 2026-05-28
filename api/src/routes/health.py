from typing import Any

from flask import current_app, jsonify
from flask_smorest import Blueprint
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.extensions import get_session_factory
from src.schemas.common import HealthSchema, ReadySchema, UnavailableSchema

health_bp = Blueprint("health", "health", description="Liveness and readiness probes")


@health_bp.route("/health")
@health_bp.response(200, HealthSchema)
def health_check() -> dict[str, str]:
    """Return a static liveness payload.

    No DB access; this endpoint is wired for nginx / Docker healthchecks only.
    """
    return {"status": "ok"}


@health_bp.route("/health/ready")
@health_bp.response(200, ReadySchema)
@health_bp.alt_response(503, schema=UnavailableSchema)
def health_ready() -> Any:
    """Verify the api can actually round-trip a query to Postgres.

    A separate endpoint from ``/health`` on purpose: Docker's
    ``healthcheck`` directive must NOT depend on Postgres reachability,
    or a transient DB blip would mark the api container ``unhealthy``
    and cascade through ``proxy: depends_on: api: service_healthy``.
    This endpoint is for external readiness probes - Gatus, the release
    workflow's post-rollout poll, future k8s ``readinessProbe``.

    Returns 200 ``{"status": "ready"}`` when ``SELECT 1`` round-trips;
    503 ``{"status": "unavailable", "reason": "db"}`` on any
    ``SQLAlchemyError`` (connect refused, timeout, pool exhausted).
    """
    try:
        session_factory = get_session_factory()
        with session_factory() as db:
            # Bound the probe so pool exhaustion or a stuck connection makes
            # the endpoint return 503 fast rather than blocking until the
            # probe interval lapses (which would mark the api unready while
            # the application itself is still serving real traffic).
            db.execute(text("SET LOCAL statement_timeout = '500ms'"))
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.warning("/health/ready: db unavailable")
        return jsonify({"status": "unavailable", "reason": "db"}), 503
    return {"status": "ready"}
