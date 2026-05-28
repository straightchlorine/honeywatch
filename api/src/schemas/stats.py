from __future__ import annotations

from marshmallow import fields, validate

from src.schemas.common import BaseSchema


class TotalsSchema(BaseSchema):
    """Headline counters returned by GET /api/stats/totals."""

    total_sessions = fields.Int(required=True)
    total_auth_attempts = fields.Int(required=True)
    unique_ips = fields.Int(required=True)


class TopPasswordSchema(BaseSchema):
    password = fields.Str(required=True, allow_none=True)
    count = fields.Int(required=True)


class TopCountrySchema(BaseSchema):
    country_code = fields.Str(required=True, allow_none=True)
    country = fields.Str(required=True, allow_none=True)
    count = fields.Int(required=True)


class TrendSchema(BaseSchema):
    current = fields.Int(required=True)
    previous = fields.Int(required=True)
    delta = fields.Int(required=True)
    pct_change = fields.Float(required=True, allow_none=True)


class ActivityBucketSchema(BaseSchema):
    bucket = fields.Str(required=True)
    count = fields.Int(required=True)


class HeatmapPointSchema(BaseSchema):
    hour = fields.Int(required=True)
    weekday = fields.Int(required=True)
    count = fields.Int(required=True)


class TopPasswordsQuerySchema(BaseSchema):
    top_n = fields.Int(load_default=10, validate=validate.Range(min=1, max=100))


class TopCountriesQuerySchema(BaseSchema):
    top_n = fields.Int(load_default=10, validate=validate.Range(min=1, max=100))


class ActivityQuerySchema(BaseSchema):
    bucket = fields.Str(
        load_default="day", validate=validate.OneOf(["hour", "day", "month"])
    )


class TrendQuerySchema(BaseSchema):
    period_days = fields.Int(load_default=7, validate=validate.Range(min=1, max=365))
