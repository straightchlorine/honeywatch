from typing import Any

from flask import current_app, jsonify
from flask_smorest import Blueprint
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.extensions import get_session_factory
from src.schemas.common import HealthResponse, ReadyResponse, UnavailableResponse

health_bp = Blueprint("health", "health", description="Liveness and readiness probes")


@health_bp.route("/health")
@health_bp.doc(operationId="healthLive")
@health_bp.response(200, HealthResponse)
def health_check() -> dict[str, str]:
    """Return a static liveness payload."""
    return {"status": "ok"}


@health_bp.route("/health/ready")
@health_bp.doc(operationId="healthReady")
@health_bp.response(200, ReadyResponse)
@health_bp.alt_response(503, schema=UnavailableResponse)
def health_ready() -> Any:
    """Return 200 when the DB is reachable, 503 otherwise."""
    # NOTE (not in spec): kept distinct from /health so a transient DB blip
    # does not cascade through docker compose service_healthy dependencies.
    # Probe bound at 500ms so pool exhaustion fails fast.
    try:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.execute(text("SET LOCAL statement_timeout = '500ms'"))
            db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        current_app.logger.warning(
            "/health/ready: db unavailable type=%s msg=%s",
            type(exc).__name__,
            str(exc)[:200],
        )
        # jsonify (not bare dict) so flask-smorest's @response(200, ReadyResponse)
        # does not reshape the 503 body through the success schema.
        return jsonify({"status": "unavailable", "reason": "db"}), 503
    return {"status": "ready"}
