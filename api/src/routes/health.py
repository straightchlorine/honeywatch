from typing import Any

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check() -> tuple[Any, int]:
    """Return a static liveness payload.

    Returns:
        ``({"status": "ok"}, 200)``. No DB access; this endpoint is wired
        for nginx / Docker healthchecks only.
    """
    return jsonify({"status": "ok"}), 200
