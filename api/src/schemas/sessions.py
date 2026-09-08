from __future__ import annotations

from marshmallow import ValidationError, fields, validate

from src.schemas.common import BaseSchema, PaginationMeta, country_filter_field
from src.services.categories import CATEGORY_DESCRIPTION, SESSION_CATEGORIES
from src.services.sessions import VALID_HAS_FILTERS


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


class _SessionResponseBase(BaseSchema):
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
    city = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "City name of the source IP, when resolved.",
            "example": "Amsterdam",
        },
    )
    lat = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Latitude of the source IP, when resolved.",
            "example": 52.4,
        },
    )
    lon = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Longitude of the source IP, when resolved.",
            "example": 4.9,
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


class SessionSummaryResponse(_SessionResponseBase):
    """List-endpoint shape; src_ip omitted like everywhere else in the API."""

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
    has_successful_login = fields.Bool(
        required=True,
        metadata={
            "description": (
                "Whether any authentication attempt in the session succeeded."
            ),
            "example": True,
        },
    )
    category = fields.Str(
        required=True,
        validate=validate.OneOf(list(SESSION_CATEGORIES)),
        metadata={"description": CATEGORY_DESCRIPTION, "example": "active"},
    )
    n_commands = fields.Int(
        required=True,
        metadata={"description": "Maintained commands counter.", "example": 3},
    )
    n_downloads = fields.Int(
        required=True,
        metadata={"description": "Maintained downloads counter.", "example": 0},
    )
    n_tcpip = fields.Int(
        required=True,
        metadata={
            "description": "Maintained direct-tcpip-request counter.",
            "example": 0,
        },
    )
    auth_success = fields.Bool(
        required=True,
        metadata={
            "description": (
                "Whether any auth attempt in the session succeeded (maintained flag)."
            ),
            "example": True,
        },
    )
    interest = fields.Int(
        required=True,
        metadata={
            "description": (
                "DB-computed interest score: "
                "2*commands + 5*downloads + 2*tcpip + 3*auth_success."
            ),
            "example": 9,
        },
    )
    asn_org = fields.Str(
        required=True,
        allow_none=True,
        metadata={"description": "Source network organisation.", "example": "OVH SAS"},
    )
    client_version = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "SSH client version string, when captured.",
            "example": "SSH-2.0-libssh2_1.10.0",
        },
    )


class SessionDetailResponse(_SessionResponseBase):
    """Detail-endpoint shape; src_ip and dst_ip omitted by API design."""

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
    max_interest = fields.Int(
        required=True,
        metadata={
            "description": (
                "Highest interest value across all sessions (unfiltered) - the "
                "ceiling row-level interest scores are normalized against for "
                "display."
            ),
            "example": 56,
        },
    )


def _validate_has(value: str) -> None:
    """Reject 'none' combined with other filters (would yield empty set)."""
    tokens = value.split(",")
    unknown = [t for t in tokens if t not in VALID_HAS_FILTERS]
    if unknown:
        raise ValidationError(
            "has= must be a comma-separated list of: "
            f"{', '.join(sorted(VALID_HAS_FILTERS))}."
        )
    if "none" in tokens and len(tokens) > 1:
        raise ValidationError(
            "has=none (no activity at all) cannot be combined with other filters."
        )


class SessionsListQuery(BaseSchema):
    page = fields.Int(
        load_default=1,
        validate=validate.Range(min=1, max=50_000),
        metadata={"description": "Page number to fetch (1-indexed).", "example": 1},
    )
    per_page = fields.Int(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={"description": "Number of items per page (max 100).", "example": 20},
    )
    q = fields.Str(
        load_default=None,
        allow_none=True,
        validate=[
            validate.Length(min=2, max=64),
            validate.Regexp(r"^[0-9a-f]+$"),
        ],
        metadata={
            "description": (
                "Session id prefix, lowercase hex only (2-64 chars). Matched "
                "with a leading-anchor search, so it never carries a LIKE "
                "wildcard."
            ),
            "example": "a1b2c3",
        },
    )
    country = country_filter_field()
    category = fields.Str(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(list(SESSION_CATEGORIES)),
        metadata={"description": CATEGORY_DESCRIPTION, "example": "active"},
    )
    sort = fields.Str(
        load_default="recent",
        validate=validate.OneOf(
            ["recent", "country", "active", "interest", "duration"]
        ),
        metadata={
            "description": (
                "Result ordering: 'recent' (newest first, default), 'country' "
                "(source country A-Z), 'active' (most commands first), "
                "'interest' (highest interest score first), 'duration' "
                "(longest session first)."
            ),
            "example": "country",
        },
    )
    has = fields.Str(
        load_default=None,
        allow_none=True,
        validate=_validate_has,
        metadata={
            "description": (
                "Comma-separated filters, all must match: 'commands' "
                "(n_commands > 0), 'downloads' (n_downloads > 0), 'success' "
                "(auth_success), 'tcpip' (n_tcpip > 0), 'none' (interest = 0, "
                "did nothing at all - mutually exclusive with the others)."
            ),
            "example": "commands,success",
        },
    )
    sha256 = fields.Str(
        load_default=None,
        allow_none=True,
        validate=validate.Regexp(r"^[0-9a-f]{64}$"),
        metadata={
            "description": (
                "Only sessions that captured this payload. Lowercase hex; the "
                "pattern is the whole defence, so the value can never reach SQL "
                "as anything but a digest."
            ),
            "example": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
        },
    )


class SessionIdPath(BaseSchema):
    session_id = fields.Str(
        required=True,
        validate=validate.Regexp(r"^[A-Za-z0-9_-]{1,64}$"),
        metadata={"description": "Session identifier.", "example": "abc-123"},
    )
