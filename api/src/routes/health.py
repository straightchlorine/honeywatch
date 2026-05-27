from typing import Any

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.extensions import get_session_factory

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check() -> tuple[Any, int]:
    """Return a static liveness payload.

    Returns:
        ``({"status": "ok"}, 200)``. No DB access; this endpoint is wired
        for nginx / Docker healthchecks only.
    """
    return jsonify({"status": "ok"}), 200


@health_bp.route("/health/ready")
def health_ready() -> tuple[Any, int]:
    """Verify the api can actually round-trip a query to Postgres.

    A separate endpoint from ``/health`` on purpose: Docker's
    ``healthcheck`` directive must NOT depend on Postgres reachability,
    or a transient DB blip would mark the api container ``unhealthy``
    and cascade through ``proxy: depends_on: api: service_healthy``.
    This endpoint is for external readiness probes - Gatus, the release
    workflow's post-rollout poll, future k8s ``readinessProbe``.

    Returns:
        ``({"status": "ready"}, 200)`` when ``SELECT 1`` round-trips.
        ``({"status": "unavailable", "reason": "db"}, 503)`` when the
        DB session raises any ``SQLAlchemyError`` (connect refused,
        timeout, pool exhausted).
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
        # DB outage - recoverable state; warn
        current_app.logger.warning("/health/ready: db unavailable")
        return jsonify({"status": "unavailable", "reason": "db"}), 503
    return jsonify({"status": "ready"}), 200
