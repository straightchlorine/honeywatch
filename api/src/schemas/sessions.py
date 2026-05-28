from __future__ import annotations

from marshmallow import fields, validate

from src.schemas.common import BaseSchema


class AuthAttemptSchema(BaseSchema):
    id = fields.Int(required=True)
    username = fields.Str(required=True)
    password = fields.Str(required=True)
    success = fields.Bool(required=True)
    timestamp = fields.Str(required=True, allow_none=True)


class CommandSchema(BaseSchema):
    id = fields.Int(required=True)
    input = fields.Str(required=True)
    success = fields.Bool(required=True, allow_none=True)
    timestamp = fields.Str(required=True, allow_none=True)


class DownloadSchema(BaseSchema):
    id = fields.Int(required=True)
    url = fields.Str(required=True, allow_none=True)
    outfile = fields.Str(required=True, allow_none=True)
    sha256 = fields.Str(required=True, allow_none=True)
    timestamp = fields.Str(required=True, allow_none=True)


class SessionSummarySchema(BaseSchema):
    """List-endpoint shape. src_ip deliberately omitted (privacy gate)."""

    id = fields.Str(required=True)
    src_port = fields.Int(required=True)
    dst_port = fields.Int(required=True)
    protocol = fields.Str(required=True)
    country_code = fields.Str(required=True, allow_none=True)
    country = fields.Str(required=True, allow_none=True)
    started_at = fields.Str(required=True, allow_none=True)
    ended_at = fields.Str(required=True, allow_none=True)
    auth_attempt_count = fields.Int(required=True)


class SessionDetailSchema(BaseSchema):
    """Detail-endpoint shape. src_ip deliberately omitted (privacy gate)."""

    id = fields.Str(required=True)
    src_port = fields.Int(required=True)
    dst_ip = fields.Str(required=True, allow_none=True)
    dst_port = fields.Int(required=True)
    protocol = fields.Str(required=True)
    country_code = fields.Str(required=True, allow_none=True)
    country = fields.Str(required=True, allow_none=True)
    started_at = fields.Str(required=True, allow_none=True)
    ended_at = fields.Str(required=True, allow_none=True)
    sensor = fields.Str(required=True, allow_none=True)
    auth_attempts = fields.List(fields.Nested(AuthAttemptSchema), required=True)
    commands = fields.List(fields.Nested(CommandSchema), required=True)
    downloads = fields.List(fields.Nested(DownloadSchema), required=True)


class SessionsListSchema(BaseSchema):
    sessions = fields.List(fields.Nested(SessionSummarySchema), required=True)
    total = fields.Int(required=True)
    page = fields.Int(required=True)
    per_page = fields.Int(required=True)
    pages = fields.Int(required=True)


class SessionsQuerySchema(BaseSchema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1, max=10_000))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
