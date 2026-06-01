from __future__ import annotations

from marshmallow import fields, validate

from src.schemas.common import BaseSchema, PaginationMeta


class AuthAttemptResponse(BaseSchema):
    id = fields.Int(
        required=True,
        metadata={"description": "Auth attempt row id.", "example": 1234},
    )
    username = fields.Str(
        required=True,
        metadata={
            "description": "Username supplied by the attacker.",
            "example": "root",
        },
    )
    password = fields.Str(
        required=True,
        metadata={
            "description": "Password supplied by the attacker.",
            "example": "123456",
        },
    )
    success = fields.Bool(
        required=True,
        metadata={
            "description": "Whether the credential pair was accepted by the honeypot.",
            "example": False,
        },
    )
    timestamp = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp of the auth attempt.",
            "example": "2026-05-28T12:34:56Z",
        },
    )


class CommandResponse(BaseSchema):
    id = fields.Int(
        required=True,
        metadata={"description": "Command row id.", "example": 4321},
    )
    input = fields.Str(
        required=True,
        metadata={
            "description": "Command line entered in the honeypot shell.",
            "example": "uname -a",
        },
    )
    success = fields.Bool(
        required=True,
        allow_none=True,
        metadata={
            "description": "Whether command was reported successful (null if unknown).",
            "example": True,
        },
    )
    timestamp = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp of when the command ran.",
            "example": "2026-05-28T12:35:10Z",
        },
    )


class DownloadResponse(BaseSchema):
    id = fields.Int(
        required=True,
        metadata={"description": "Download row id.", "example": 99},
    )
    url = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Source URL the attacker attempted to fetch.",
            "example": "http://example.invalid/payload.sh",
        },
    )
    outfile = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Local path where the honeypot saved the captured payload.",
            "example": "/data/downloads/abc123",
        },
    )
    sha256 = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "SHA-256 hex digest of the captured payload.",
            "example": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
        },
    )
    timestamp = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp of the download event.",
            "example": "2026-05-28T12:36:00Z",
        },
    )


class SessionSummaryResponse(BaseSchema):
    """List-endpoint shape. src_ip deliberately omitted (privacy gate)."""

    id = fields.Str(
        required=True,
        metadata={"description": "Honeypot session identifier.", "example": "abc123"},
    )
    src_port = fields.Int(
        required=True,
        metadata={
            "description": "Source TCP port of the attacker connection.",
            "example": 51234,
        },
    )
    dst_port = fields.Int(
        required=True,
        metadata={
            "description": "Destination TCP port that received the connection.",
            "example": 22,
        },
    )
    protocol = fields.Str(
        required=True,
        metadata={"description": "Application protocol observed.", "example": "ssh"},
    )
    country_code = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 3166-1 alpha-2 country code of the source IP.",
            "example": "US",
        },
    )
    country = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Human-readable country name of the source IP.",
            "example": "United States",
        },
    )
    started_at = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp when the session began.",
            "example": "2026-05-28T12:34:00Z",
        },
    )
    ended_at = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp when the session ended.",
            "example": "2026-05-28T12:40:00Z",
        },
    )
    auth_attempt_count = fields.Int(
        required=True,
        metadata={
            "description": "Number of authentication attempts in this session.",
            "example": 5,
        },
    )
    command_count = fields.Int(
        required=True,
        metadata={
            "description": "Number of shell commands recorded in this session.",
            "example": 3,
        },
    )
    login_success = fields.Bool(
        required=True,
        metadata={
            "description": (
                "Whether any authentication attempt in the session succeeded."
            ),
            "example": True,
        },
    )


class SessionDetailResponse(BaseSchema):
    """Detail-endpoint shape. src_ip deliberately omitted (privacy gate)."""

    id = fields.Str(
        required=True,
        metadata={"description": "Honeypot session identifier.", "example": "abc123"},
    )
    src_port = fields.Int(
        required=True,
        metadata={
            "description": "Source TCP port of the attacker connection.",
            "example": 51234,
        },
    )
    dst_ip = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Destination IP address of the honeypot.",
            "example": "10.0.0.5",
        },
    )
    dst_port = fields.Int(
        required=True,
        metadata={
            "description": "Destination TCP port that received the connection.",
            "example": 22,
        },
    )
    protocol = fields.Str(
        required=True,
        metadata={"description": "Application protocol observed.", "example": "ssh"},
    )
    country_code = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 3166-1 alpha-2 country code of the source IP.",
            "example": "US",
        },
    )
    country = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Human-readable country name of the source IP.",
            "example": "United States",
        },
    )
    started_at = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp when the session began.",
            "example": "2026-05-28T12:34:00Z",
        },
    )
    ended_at = fields.DateTime(
        required=True,
        allow_none=True,
        format="iso",
        metadata={
            "description": "ISO 8601 UTC timestamp when the session ended.",
            "example": "2026-05-28T12:40:00Z",
        },
    )
    sensor = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Identifier of the sensor that captured the session.",
            "example": "sensor-01",
        },
    )
    auth_attempts = fields.List(
        fields.Nested(AuthAttemptResponse),
        required=True,
        metadata={
            "description": "Authentication attempts recorded during the session."
        },
    )
    commands = fields.List(
        fields.Nested(CommandResponse),
        required=True,
        metadata={"description": "Commands executed during the session."},
    )
    downloads = fields.List(
        fields.Nested(DownloadResponse),
        required=True,
        metadata={"description": "File download attempts recorded during the session."},
    )


class SessionsListResponse(BaseSchema):
    items = fields.List(
        fields.Nested(SessionSummaryResponse),
        required=True,
        metadata={"description": "Page of session summaries."},
    )
    meta = fields.Nested(
        PaginationMeta,
        required=True,
        metadata={"description": "Pagination metadata for the response page."},
    )


class SessionsListQuery(BaseSchema):
    page = fields.Int(
        load_default=1,
        validate=validate.Range(min=1, max=10_000),
        metadata={"description": "Page number to fetch (1-indexed).", "example": 1},
    )
    per_page = fields.Int(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={"description": "Number of items per page (max 100).", "example": 20},
    )
    country = fields.Str(
        load_default=None,
        allow_none=True,
        validate=validate.Regexp(r"^[A-Za-z]{2}$"),
        metadata={
            "description": "Filter to a single ISO 3166-1 alpha-2 source country.",
            "example": "CN",
        },
    )
    category = fields.Str(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["active", "login", "failed", "probe"]),
        metadata={
            "description": (
                "Filter by session classification (mutually exclusive): "
                "'active' = ran at least one command; 'login' = login accepted "
                "but no commands; 'failed' = login attempts made, none accepted; "
                "'probe' = connection only, no login attempts."
            ),
            "example": "active",
        },
    )
    sort = fields.Str(
        load_default="recent",
        validate=validate.OneOf(["recent", "country", "active"]),
        metadata={
            "description": (
                "Result ordering: 'recent' (newest first, default), 'country' "
                "(source country A-Z), 'active' (most commands first)."
            ),
            "example": "country",
        },
    )


class SessionIdPath(BaseSchema):
    session_id = fields.Str(
        required=True,
        validate=validate.Regexp(r"^[A-Za-z0-9_-]{1,64}$"),
        metadata={"description": "Session identifier.", "example": "abc-123"},
    )
