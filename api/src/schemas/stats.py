from __future__ import annotations

from marshmallow import fields, validate

from src.schemas.common import BaseSchema, country_filter_field
from src.services.stats import (
    PASSWORD_LENGTH_CAP,
    VALID_BUCKETS,
    VALID_CRED_GROUPINGS,
    VALID_CRED_METRICS,
    VALID_CRED_OUTCOMES,
)


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


class PasswordsByLengthQuery(BaseSchema):
    """Query args for the password-length drill-down (Credentials histogram)."""

    length = fields.Int(
        required=True,
        validate=validate.Range(min=0, max=PASSWORD_LENGTH_CAP),
        metadata={
            "description": (
                "Password length to list. At the cap this lists every password "
                "of that length or longer (the histogram's tail bucket)."
            ),
            "example": 6,
        },
    )
    top_n = fields.Int(
        load_default=10,
        validate=validate.Range(min=1, max=100),
        metadata={
            "description": "Number of top entries to return (max 100).",
            "example": 10,
        },
    )


class TopCredentialResponse(BaseSchema):
    username = fields.Str(
        required=True,
        allow_none=True,
        metadata={"description": "Username attempted.", "example": "root"},
    )
    password = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Password attempted (null when grouping by username).",
            "example": "123456",
        },
    )
    count = fields.Int(
        required=True,
        metadata={
            "description": "Number of attempts for this credential.",
            "example": 128,
        },
    )
    distinct_ips = fields.Int(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Distinct source addresses that tried this credential; only "
                "populated for the ip_fanout metric (null otherwise). A high "
                "value signals a distributed botnet sharing one credential."
            ),
            "example": 42,
        },
    )


class AuthOutcomesResponse(BaseSchema):
    total = fields.Int(
        required=True,
        metadata={"description": "Total auth attempts recorded.", "example": 9876},
    )
    successful = fields.Int(
        required=True,
        metadata={"description": "Attempts cowrie accepted.", "example": 178},
    )
    failed = fields.Int(
        required=True,
        metadata={"description": "Attempts cowrie rejected.", "example": 9698},
    )
    success_rate = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Accepted percentage (null when there are no attempts).",
            "example": 1.8,
        },
    )
    unique_passwords = fields.Int(
        required=True,
        metadata={
            "description": "Distinct passwords attempted (attacker wordlist size).",
            "example": 412,
        },
    )
    unique_usernames = fields.Int(
        required=True,
        metadata={
            "description": "Distinct usernames attempted.",
            "example": 57,
        },
    )


class CredentialLengthResponse(BaseSchema):
    length = fields.Int(
        required=True,
        metadata={
            "description": "Password length (capped; the top bucket is the tail).",
            "example": 6,
        },
    )
    count = fields.Int(
        required=True,
        metadata={
            "description": "Number of attempts with this password length.",
            "example": 311,
        },
    )


class CharsetClassResponse(BaseSchema):
    name = fields.Str(
        required=True,
        metadata={
            "description": (
                "Charset class: empty | symbol | digits | lower | upper | alnum."
            ),
            "example": "digits",
        },
    )
    count = fields.Int(
        required=True,
        metadata={
            "description": "Number of attempts in this charset class.",
            "example": 204,
        },
    )


class PasswordCompositionResponse(BaseSchema):
    total = fields.Int(
        required=True,
        metadata={"description": "Total passwords classified.", "example": 9876},
    )
    capped_at = fields.Int(
        required=True,
        metadata={
            "description": "Length cap; the top length bucket is this value or more.",
            "example": 16,
        },
    )
    lengths = fields.List(
        fields.Nested(CredentialLengthResponse),
        required=True,
        metadata={"description": "Password-length histogram, ascending by length."},
    )
    classes = fields.List(
        fields.Nested(CharsetClassResponse),
        required=True,
        metadata={"description": "Charset-class breakdown, descending by count."},
    )


class TopCredentialsQuery(BaseSchema):
    """Query args for the credential leaderboard (Credentials page)."""

    by = fields.Str(
        load_default="pair",
        validate=validate.OneOf(sorted(VALID_CRED_GROUPINGS)),
        metadata={
            "description": (
                "Group by username+password ('pair'), username only, or "
                "password only (the raw most-common-passwords view)."
            ),
            "example": "pair",
        },
    )
    metric = fields.Str(
        load_default="attempts",
        validate=validate.OneOf(sorted(VALID_CRED_METRICS)),
        metadata={
            "description": "Rank by raw attempt count or distinct-IP fan-out.",
            "example": "attempts",
        },
    )
    outcome = fields.Str(
        load_default="any",
        validate=validate.OneOf(sorted(VALID_CRED_OUTCOMES)),
        metadata={
            "description": "Filter to cowrie-accepted, rejected, or all attempts.",
            "example": "any",
        },
    )
    top_n = fields.Int(
        load_default=10,
        validate=validate.Range(min=1, max=100),
        metadata={
            "description": "Number of top entries to return (max 100).",
            "example": 10,
        },
    )


class ActivityQuery(BaseSchema):
    bucket = fields.Str(
        load_default="day",
        validate=validate.OneOf(sorted(VALID_BUCKETS)),
        metadata={"description": "Aggregation bucket width.", "example": "day"},
    )
    country = country_filter_field()


class TrendQuery(BaseSchema):
    period_days = fields.Int(
        load_default=7,
        validate=validate.Range(min=1, max=365),
        metadata={
            "description": "Length of the comparison window in days.",
            "example": 7,
        },
    )
    country = country_filter_field()


class HeatmapQuery(BaseSchema):
    country = country_filter_field()
