from typing import Any

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check() -> tuple[Any, int]:
    return jsonify({"status": "ok"}), 200
