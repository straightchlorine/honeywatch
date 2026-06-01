from __future__ import annotations

from marshmallow import fields, validate

from src.schemas.common import BaseSchema
from src.services.stats import VALID_BUCKETS


class TotalsResponse(BaseSchema):
    """Headline counters returned by GET /api/v1/stats/totals."""

    total_sessions = fields.Int(
        required=True,
        metadata={
            "description": "Total number of honeypot sessions recorded.",
            "example": 1234,
        },
    )
    total_auth_attempts = fields.Int(
        required=True,
        metadata={
            "description": "Total auth attempts across all sessions.",
            "example": 9876,
        },
    )
    unique_ips = fields.Int(
        required=True,
        metadata={
            "description": "Number of distinct source IP addresses observed.",
            "example": 321,
        },
    )


class TopPasswordResponse(BaseSchema):
    password = fields.Str(
        required=True,
        allow_none=True,
        metadata={"description": "Password value attempted.", "example": "123456"},
    )
    count = fields.Int(
        required=True,
        metadata={
            "description": "Number of times this password was attempted.",
            "example": 42,
        },
    )


class TopCountryResponse(BaseSchema):
    country_code = fields.Str(
        required=True,
        allow_none=True,
        metadata={"description": "ISO 3166-1 alpha-2 country code.", "example": "CN"},
    )
    country = fields.Str(
        required=True,
        allow_none=True,
        metadata={"description": "Human-readable country name.", "example": "China"},
    )
    count = fields.Int(
        required=True,
        metadata={
            "description": "Number of sessions originating from this country.",
            "example": 137,
        },
    )


class TrendResponse(BaseSchema):
    current = fields.Int(
        required=True,
        metadata={"description": "Count for the current period.", "example": 100},
    )
    previous = fields.Int(
        required=True,
        metadata={
            "description": "Count for the prior period of equal length.",
            "example": 80,
        },
    )
    delta = fields.Int(
        required=True,
        metadata={
            "description": "Absolute difference (current - previous).",
            "example": 20,
        },
    )
    pct_change = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Percentage change (null if previous is zero).",
            "example": 25.0,
        },
    )


class ActivityBucketResponse(BaseSchema):
    bucket = fields.Str(
        required=True,
        metadata={
            "description": "Bucket label (ISO 8601 truncated to bucket width).",
            "example": "2026-05-28",
        },
    )
    count = fields.Int(
        required=True,
        metadata={"description": "Number of sessions in the bucket.", "example": 17},
    )


class HeatmapPointResponse(BaseSchema):
    hour = fields.Int(
        required=True,
        metadata={"description": "Hour of day (0-23, UTC).", "example": 14},
    )
    weekday = fields.Int(
        required=True,
        metadata={
            "description": "Day of week, Postgres dow (0=Sunday, 6=Saturday).",
            "example": 2,
        },
    )
    count = fields.Int(
        required=True,
        metadata={
            "description": "Number of sessions in this hour/weekday cell.",
            "example": 8,
        },
    )


class TopNQuery(BaseSchema):
    """Shared query args for the top-N leaderboards (passwords, countries)."""

    top_n = fields.Int(
        load_default=10,
        validate=validate.Range(min=1, max=100),
        metadata={
            "description": "Number of top entries to return (max 100).",
            "example": 10,
        },
    )


def _country_field() -> fields.Str:
    """Fresh optional alpha-2 country filter field (one instance per schema)."""
    return fields.Str(
        load_default=None,
        allow_none=True,
        validate=validate.Regexp(r"^[A-Za-z]{2}$"),
        metadata={
            "description": "Scope to a single ISO 3166-1 alpha-2 source country.",
            "example": "CN",
        },
    )


class ActivityQuery(BaseSchema):
    bucket = fields.Str(
        load_default="day",
        validate=validate.OneOf(sorted(VALID_BUCKETS)),
        metadata={"description": "Aggregation bucket width.", "example": "day"},
    )
    country = _country_field()


class TrendQuery(BaseSchema):
    period_days = fields.Int(
        load_default=7,
        validate=validate.Range(min=1, max=365),
        metadata={
            "description": "Length of the comparison window in days.",
            "example": 7,
        },
    )
    country = _country_field()


class HeatmapQuery(BaseSchema):
    country = _country_field()
