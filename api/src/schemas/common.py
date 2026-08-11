from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from marshmallow import Schema, fields, validate


class CountryCodeField(fields.String):
    """Country-code string that upper-cases on load.

    MaxMind stores alpha-2 codes upper-case. Validator accepts either.
    """

    def _deserialize(
        self,
        value: Any,
        attr: str | None,
        data: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> str:
        return super()._deserialize(value, attr, data, **kwargs).upper()


def country_filter_field() -> fields.Str:
    """Optional alpha-2 country filter.

    A factory, not a shared instance: marshmallow binds a field to its owning
    schema, so reusing one across schemas breaks.
    """
    return CountryCodeField(
        load_default=None,
        allow_none=True,
        validate=validate.Regexp(r"^[A-Za-z]{2}$"),
        metadata={
            "description": "Scope to a single ISO 3166-1 alpha-2 source country.",
            "example": "CN",
        },
    )


def top_n_field(
    default: int, description: str = "Number of top entries to return"
) -> fields.Int:
    """Top-N limit field; a factory since marshmallow binds fields to schemas."""
    return fields.Int(
        load_default=default,
        validate=validate.Range(min=1, max=100),
        metadata={"description": f"{description} (max 100).", "example": default},
    )


def country_or_unknown_field() -> fields.Str:
    """Country filter that also accepts "??".

    The credential and ASN leaderboards are reachable by clicking a row on the
    Countries page, including its Unknown row - "??" addresses that bucket.
    """
    return CountryCodeField(
        load_default=None,
        allow_none=True,
        validate=validate.Regexp(r"^([A-Za-z]{2}|\?\?)$"),
        metadata={
            "description": (
                "Scope to a single ISO 3166-1 alpha-2 source country, or '??' "
                "for the geo-less (Unknown) bucket."
            ),
            "example": "CN",
        },
    )


class BaseSchema(Schema):
    """Shared base for every schema.

    Empty on purpose: marshmallow 4 keeps field declaration order, so the
    generated OpenAPI is stable without any Meta config.
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
