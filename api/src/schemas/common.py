from __future__ import annotations

from marshmallow import Schema, fields


class BaseSchema(Schema):
    """Project-wide base schema.

    ``ordered = True`` keeps generated OpenAPI properties in declaration order
    so the spec (and any committed ``openapi.json`` / ``schema.d.ts``)
    produces stable diffs across regenerations.
    """

    class Meta:
        ordered = True


class ErrorSchema(BaseSchema):
    """JSON error envelope used by 4xx/5xx handlers."""

    error = fields.Str(required=True)
    code = fields.Int(required=False)


class HealthSchema(BaseSchema):
    """Liveness payload."""

    status = fields.Str(required=True)


class ReadySchema(BaseSchema):
    """Readiness payload (200 path)."""

    status = fields.Str(required=True)


class UnavailableSchema(BaseSchema):
    """Readiness payload (503 path)."""

    status = fields.Str(required=True)
    reason = fields.Str(required=True)
