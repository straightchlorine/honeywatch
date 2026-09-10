from __future__ import annotations

from marshmallow import fields, validate

from src.schemas.common import (
    BaseSchema,
    CountryCodeField,
    country_filter_field,
    country_or_unknown_field,
    sort_order_field,
    top_n_field,
)
from src.services.stats.activity import VALID_BUCKETS
from src.services.stats.countries import VALID_COUNTRY_SORTS
from src.services.stats.credentials import (
    PASSWORD_LENGTH_CAP,
    VALID_CRED_GROUPINGS,
    VALID_CRED_METRICS,
    VALID_CRED_OUTCOMES,
)


class TotalsResponse(BaseSchema):
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


class CountryRowResponse(BaseSchema):
    """One country's full attack breakdown (Countries leaderboard row)."""

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
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions from this country.",
            "example": 137,
        },
    )
    distinct_ips = fields.Int(
        required=True,
        metadata={
            "description": "Distinct source IPs from this country (fan-out width).",
            "example": 42,
        },
    )
    attempts = fields.Int(
        required=True,
        metadata={"description": "Auth attempts from this country.", "example": 512},
    )
    successful = fields.Int(
        required=True,
        metadata={"description": "Attempts cowrie accepted.", "example": 3},
    )
    success_rate = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Accepted percentage (null when no attempts).",
            "example": 0.59,
        },
    )


class CountriesResponse(BaseSchema):
    countries = fields.List(
        fields.Nested(CountryRowResponse),
        required=True,
        metadata={"description": "Per-country rows, ranked by the chosen sort."},
    )
    total_countries = fields.Int(
        required=True,
        metadata={
            "description": "Distinct resolved countries (excludes the Unknown bucket).",
            "example": 47,
        },
    )
    geo_resolved_pct = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Percent of sessions with resolved geolocation (null if no "
                "sessions); the rest falls under the Unknown bucket."
            ),
            "example": 81.3,
        },
    )


class AsnResponse(BaseSchema):
    """One source network (ASN / org) in the Countries detail breakdown."""

    asn = fields.Int(
        required=True,
        allow_none=True,
        metadata={"description": "Autonomous System Number.", "example": 16276},
    )
    as_org = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Autonomous System organisation.",
            "example": "OVH SAS",
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={"description": "Distinct sessions from this network.", "example": 88},
    )
    distinct_ips = fields.Int(
        required=True,
        metadata={
            "description": "Distinct source IPs from this network.",
            "example": 12,
        },
    )


class MapCountryResponse(BaseSchema):
    """One country's choropleth-ready metric row (Overview map deck)."""

    a2 = fields.Str(
        required=True,
        metadata={"description": "ISO 3166-1 alpha-2 country code.", "example": "CN"},
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions from this country.",
            "example": 137,
        },
    )
    ips = fields.Int(
        required=True,
        metadata={
            "description": "Distinct source IPs from this country.",
            "example": 42,
        },
    )
    success_rate = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Accepted percentage (null when no attempts).",
            "example": 0.59,
        },
    )


class MapCityResponse(BaseSchema):
    """One city marker on the Overview map deck."""

    city = fields.Str(
        required=True,
        metadata={"description": "City name.", "example": "Shanghai"},
    )
    country_code = fields.Str(
        required=True,
        metadata={"description": "ISO 3166-1 alpha-2 country code.", "example": "CN"},
    )
    lat = fields.Float(
        required=True,
        metadata={
            "description": "Latitude (jittered, rounded to 0.1 deg).",
            "example": 31.2,
        },
    )
    lon = fields.Float(
        required=True,
        metadata={
            "description": "Longitude (jittered, rounded to 0.1 deg).",
            "example": 121.5,
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={"description": "Distinct sessions from this marker.", "example": 88},
    )


class MapResponse(BaseSchema):
    """One payload for the Overview map deck: choropleth + city markers."""

    countries = fields.List(
        fields.Nested(MapCountryResponse),
        required=True,
        metadata={"description": "Every resolved country, choropleth-ready."},
    )
    cities = fields.List(
        fields.Nested(MapCityResponse),
        required=True,
        metadata={"description": "Top city markers by session count."},
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

    top_n = top_n_field(10)


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
    top_n = top_n_field(10)


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
                "Distinct source IPs that tried this credential (ip_fanout "
                "metric only, null otherwise); high values suggest a botnet."
            ),
            "example": 42,
        },
    )


class DailyPointResponse(BaseSchema):
    date = fields.Str(
        required=True,
        metadata={
            "description": "ISO 8601 date (YYYY-MM-DD).",
            "example": "2026-08-10",
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={"description": "Sessions on this date.", "example": 12},
    )


class CountryDetailResponse(BaseSchema):
    """Full country intel-drawer bundle."""

    a2 = fields.Str(
        required=True,
        metadata={"description": "ISO 3166-1 alpha-2 country code.", "example": "CN"},
    )
    name = fields.Str(
        required=True,
        metadata={"description": "Human-readable country name.", "example": "China"},
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions from this country.",
            "example": 137,
        },
    )
    ips = fields.Int(
        required=True,
        metadata={
            "description": "Distinct source IPs from this country.",
            "example": 42,
        },
    )
    attempts = fields.Int(
        required=True,
        metadata={"description": "Auth attempts from this country.", "example": 512},
    )
    success_rate = fields.Float(
        required=True,
        allow_none=True,
        metadata={
            "description": "Accepted percentage (null when no attempts).",
            "example": 0.59,
        },
    )
    top_asns = fields.List(
        fields.Nested(AsnResponse),
        required=True,
        metadata={"description": "Top source networks for this country."},
    )
    top_credentials = fields.List(
        fields.Nested(TopCredentialResponse),
        required=True,
        metadata={"description": "Top attempted credentials for this country."},
    )
    daily = fields.List(
        fields.Nested(DailyPointResponse),
        required=True,
        metadata={"description": "Session counts for the trailing 14 days."},
    )
    top_cities = fields.List(
        fields.Nested(MapCityResponse),
        required=True,
        metadata={
            "description": "Top 5 cities by session count for this country,"
            " empty if none resolved."
        },
    )


class CountryDetailPath(BaseSchema):
    a2 = CountryCodeField(
        required=True,
        validate=validate.Regexp(r"^[A-Za-z]{2}$"),
        metadata={"description": "ISO 3166-1 alpha-2 country code.", "example": "CN"},
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


class OutcomeCountsResponse(BaseSchema):
    """Facet counts for the Sessions page Outcome filter panel.

    Buckets deliberately OVERLAP - a session with both a shell and executed
    commands counts in both `shell` and `commands` - except `none`, which is
    the complement of the other four. They do not sum to `total`.
    """

    shell = fields.Int(
        required=True,
        metadata={
            "description": "Sessions with an accepted login (auth_success).",
            "example": 178,
        },
    )
    commands = fields.Int(
        required=True,
        metadata={
            "description": "Sessions with at least one executed command.",
            "example": 92,
        },
    )
    tcpip = fields.Int(
        required=True,
        metadata={
            "description": "Sessions with at least one direct-tcpip request.",
            "example": 14,
        },
    )
    downloads = fields.Int(
        required=True,
        metadata={
            "description": "Sessions with at least one download.",
            "example": 37,
        },
    )
    none = fields.Int(
        required=True,
        metadata={
            "description": (
                "Sessions with none of the above (interest == 0) - the "
                "complement of the other four buckets, not an overlap member."
            ),
            "example": 9500,
        },
    )
    total = fields.Int(
        required=True,
        metadata={"description": "Every session in scope.", "example": 9876},
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
    country = country_or_unknown_field()
    top_n = top_n_field(10)


class CountriesQuery(BaseSchema):
    """Query args for the country leaderboard (Countries page)."""

    sort = fields.Str(
        load_default="sessions",
        validate=validate.OneOf(sorted(VALID_COUNTRY_SORTS)),
        metadata={
            "description": (
                "Ranking metric: sessions, ips (distinct source IPs), attempts, "
                "or success_rate."
            ),
            "example": "sessions",
        },
    )
    order = sort_order_field()
    top_n = top_n_field(50, "Number of countries to return")


class AsnQuery(BaseSchema):
    """Query args for the source-network (ASN) breakdown."""

    country = country_or_unknown_field()
    top_n = top_n_field(10, "Number of networks to return")


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


class OutcomesQuery(BaseSchema):
    """Query args for the Outcome filter panel's facet counts."""

    country = country_filter_field()


class SshClientResponse(BaseSchema):
    """One SSH client version in the Origins client leaderboard."""

    client_version = fields.Str(
        required=True,
        metadata={
            "description": "SSH client version string (banner or key exchange).",
            "example": "libssh_0.8.9",
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Number of sessions using this client version.",
            "example": 42,
        },
    )


class FingerprintResponse(BaseSchema):
    """One SSH public key fingerprint in the Origins fingerprints leaderboard."""

    fingerprint = fields.Str(
        required=True,
        metadata={
            "description": "SSH public key fingerprint (hex digest).",
            "example": "5b:d1:07:8a:3f:01:7c:c9:8d:e2:6b:5f:94:a3:7c:2e",
        },
    )
    fingerprint_type = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "Fingerprint algorithm (e.g. 'ssh-rsa', 'ssh-ed25519').",
            "example": "ssh-rsa",
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Number of distinct sessions offering this fingerprint.",
            "example": 28,
        },
    )
    ips = fields.Int(
        required=True,
        metadata={
            "description": "Number of distinct source IPs offering this fingerprint.",
            "example": 7,
        },
    )
    first_seen = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 8601 timestamp of the first observation (or null).",
            "example": "2026-08-01T12:04:31+00:00",
        },
    )
    last_seen = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "ISO 8601 timestamp of the most recent observation (or null)."
            ),
            "example": "2026-08-11T23:59:59+00:00",
        },
    )


class PayloadDownloadResponse(BaseSchema):
    """One downloaded payload (aggregated by SHA256)."""

    sha256 = fields.Str(
        required=True,
        metadata={
            "description": "SHA256 hash of the downloaded file.",
            "example": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85"
            ),
        },
    )
    name = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Filename parsed from the most common download URL (never the "
                "honeypot's local storage path); null if no URL was recorded."
            ),
            "example": "exploit.sh",
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions that downloaded this payload.",
            "example": 42,
        },
    )
    machines = fields.Int(
        required=True,
        metadata={
            "description": (
                "Distinct source machines behind those sessions. A count, never "
                "an address. Sessions close to machines means a distributed "
                "botnet; sessions well above machines means one operator "
                "fetching repeatedly."
            ),
            "example": 40,
        },
    )
    first_seen = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 8601 timestamp of first download.",
            "example": "2026-08-10T14:30:00+00:00",
        },
    )
    last_seen = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 8601 timestamp of last download.",
            "example": "2026-08-11T09:15:00+00:00",
        },
    )
    countries = fields.List(
        fields.Str,
        required=True,
        metadata={
            "description": "Top 3 country alpha-2 codes by session count.",
            "example": ["CN", "RU", "US"],
        },
    )
    host = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Host the payload was fetched from, or null when cowrie "
                "recorded no URL or its host was a bare IP. Never an IP, and "
                "never a stand-in for one."
            ),
            "example": "attacker.example.com",
        },
    )


class PayloadDetailPath(BaseSchema):
    sha256 = fields.Str(
        required=True,
        metadata={
            "description": "SHA256 hash of the payload.",
            "example": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
        },
    )


class PayloadCountryRowResponse(BaseSchema):
    """One country's aggregated downloads for a payload detail."""

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
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions downloading from this country.",
            "example": 15,
        },
    )


class PayloadDetailResponse(BaseSchema):
    """Full detail for one downloaded payload (click-to-expand card)."""

    sha256 = fields.Str(
        required=True,
        metadata={
            "description": "SHA256 hash of the downloaded file.",
            "example": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85"
            ),
        },
    )
    name = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Filename parsed from the most common download URL (never the "
                "honeypot's local storage path); null if no URL was recorded."
            ),
            "example": "exploit.sh",
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions that downloaded this payload.",
            "example": 42,
        },
    )
    first_seen = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 8601 timestamp of first download.",
            "example": "2026-08-10T14:30:00+00:00",
        },
    )
    last_seen = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": "ISO 8601 timestamp of last download.",
            "example": "2026-08-11T09:15:00+00:00",
        },
    )
    countries = fields.List(
        fields.Nested(PayloadCountryRowResponse),
        required=True,
        metadata={
            "description": "All countries ranked by session count, descending.",
            "example": [
                {"country_code": "CN", "country": "China", "sessions": 25},
                {"country_code": "RU", "country": "Russia", "sessions": 12},
            ],
        },
    )


class TcpipDestinationResponse(BaseSchema):
    """One direct-tcpip relay target, grouped by destination network and port."""

    network = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Destination network: the AS org, or the destination itself "
                "when it is a DNS name. Null when neither is known. Never an IP."
            ),
            "example": "Cloudflare, Inc.",
        },
    )
    port = fields.Int(
        required=True,
        metadata={
            "description": "Destination port.",
            "example": 3306,
        },
    )
    sessions = fields.Int(
        required=True,
        metadata={
            "description": "Distinct sessions attempting this network and port.",
            "example": 8,
        },
    )
    hosts = fields.Int(
        required=True,
        metadata={
            "description": "Distinct destination hosts behind this network and port.",
            "example": 12,
        },
    )
    country_code = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "ISO 3166-1 alpha-2 country code for the destination network, "
                "or null if unresolved."
            ),
            "example": "US",
        },
    )
    country = fields.Str(
        required=True,
        allow_none=True,
        metadata={
            "description": (
                "Human-readable country name for the destination network, or "
                "null if unresolved."
            ),
            "example": "United States",
        },
    )
