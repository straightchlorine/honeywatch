from __future__ import annotations

from marshmallow import Schema, fields


class BaseSchema(Schema):
    """Project-wide base schema.

    Marshmallow 4 preserves field declaration order natively, so OpenAPI
    properties stay in a stable order across regenerations without any ``Meta``
    config (the old ``ordered = True`` is a no-op on MM4). Kept as the shared
    base for future cross-cutting schema config.
    """


class PaginationMeta(BaseSchema):
    """Reusable pagination envelope embedded in list responses."""

    page = fields.Int(
        required=True,
        metadata={"description": "Current page number (1-indexed).", "example": 1},
    )
    per_page = fields.Int(
        required=True,
        metadata={"description": "Number of items per page.", "example": 20},
    )
    pages = fields.Int(
        required=True,
        metadata={"description": "Total number of pages available.", "example": 5},
    )
    total = fields.Int(
        required=True,
        metadata={
            "description": "Total number of items across all pages.",
            "example": 97,
        },
    )


class HealthResponse(BaseSchema):
    """Liveness payload."""

    status = fields.Str(
        required=True,
        metadata={"description": "Liveness status string.", "example": "ok"},
    )


class ReadyResponse(BaseSchema):
    """Readiness payload (200 path)."""

    status = fields.Str(
        required=True,
        metadata={"description": "Readiness status string.", "example": "ready"},
    )


class UnavailableResponse(BaseSchema):
    """Readiness payload (503 path)."""

    status = fields.Str(
        required=True,
        metadata={"description": "Readiness status string.", "example": "unavailable"},
    )
    reason = fields.Str(
        required=True,
        metadata={
            "description": "Human-readable reason the service is unavailable.",
            "example": "database connection failed",
        },
    )
