from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class AuthAttemptDict(TypedDict):
    id: int
    username: str
    password: str
    success: bool
    timestamp: datetime | None


class CommandDict(TypedDict):
    id: int
    input: str
    success: bool | None
    timestamp: datetime | None


class DownloadDict(TypedDict):
    id: int
    url: str | None
    outfile: str | None
    sha256: str | None
    timestamp: datetime | None


class SessionBaseDict(TypedDict):
    id: str
    src_port: int
    dst_port: int
    protocol: str
    country_code: str | None
    country: str | None
    started_at: datetime | None
    ended_at: datetime | None


class SessionSummaryDict(SessionBaseDict):
    auth_attempt_count: int
    command_count: int
    has_successful_login: bool
    category: str


class SessionDetailDict(SessionBaseDict):
    sensor: str | None
    auth_attempts: list[AuthAttemptDict]
    commands: list[CommandDict]
    downloads: list[DownloadDict]


class SessionsPageDict(TypedDict):
    sessions: list[SessionSummaryDict]
    total: int
    page: int
    per_page: int
    pages: int


class TopPasswordDict(TypedDict):
    password: str
    count: int


class TopCountryDict(TypedDict):
    country_code: str | None
    country: str | None
    count: int


class ActivityBucketDict(TypedDict):
    bucket: str
    count: int


class TrendDict(TypedDict):
    current: int
    previous: int
    delta: int
    pct_change: float | None


class HeatmapPointDict(TypedDict):
    hour: int
    weekday: int
    count: int


class TotalsDict(TypedDict):
    total_sessions: int
    total_auth_attempts: int
    unique_ips: int


class TopCredentialDict(TypedDict):
    username: str | None
    password: str | None
    count: int
    distinct_ips: int | None


class AuthOutcomesDict(TypedDict):
    total: int
    successful: int
    failed: int
    success_rate: float | None
    unique_passwords: int
    unique_usernames: int


class CredentialLengthDict(TypedDict):
    length: int
    count: int


class CharsetClassDict(TypedDict):
    name: str
    count: int


class PasswordCompositionDict(TypedDict):
    total: int
    capped_at: int
    lengths: list[CredentialLengthDict]
    classes: list[CharsetClassDict]


class CountryRowDict(TypedDict):
    country_code: str | None
    country: str | None
    sessions: int
    distinct_ips: int
    attempts: int
    successful: int
    success_rate: float | None
    distinct_usernames: int
    distinct_passwords: int


class CountriesDict(TypedDict):
    countries: list[CountryRowDict]
    total_countries: int
    geo_resolved_pct: float | None


class CountryAsnDict(TypedDict):
    asn: int | None
    as_org: str | None
    sessions: int
    distinct_ips: int
