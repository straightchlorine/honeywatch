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
    sha256: str | None
    timestamp: datetime | None


class SessionBaseDict(TypedDict):
    id: str
    src_port: int
    dst_port: int
    protocol: str
    country_code: str | None
    country: str | None
    city: str | None
    lat: float | None
    lon: float | None
    started_at: datetime | None
    ended_at: datetime | None


class SessionSummaryDict(SessionBaseDict):
    auth_attempt_count: int
    command_count: int
    has_successful_login: bool
    category: str
    n_commands: int
    n_downloads: int
    n_tcpip: int
    auth_success: bool
    interest: int
    asn_org: str | None
    client_version: str | None


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
    max_interest: int


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


class OutcomeCountsDict(TypedDict):
    """Session counts per outcome bucket; buckets overlap except `none`, which is the
    complement of the rest."""

    shell: int
    commands: int
    tcpip: int
    downloads: int
    none: int
    total: int


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


class MapCountryDict(TypedDict):
    """One country's choropleth-ready metric row (Overview map deck)."""

    a2: str
    sessions: int
    ips: int
    success_rate: float | None


class MapCityDict(TypedDict):
    """One city marker on the Overview map deck."""

    city: str
    country_code: str
    lat: float
    lon: float
    sessions: int


class MapDataDict(TypedDict):
    """One payload for the Overview map deck: choropleth + city markers."""

    countries: list[MapCountryDict]
    cities: list[MapCityDict]


class DailyPointDict(TypedDict):
    date: str
    sessions: int


class CountryDetailDict(TypedDict):
    """Full country intel-drawer bundle."""

    a2: str
    name: str
    sessions: int
    ips: int
    attempts: int
    success_rate: float | None
    top_asns: list[CountryAsnDict]
    top_credentials: list[TopCredentialDict]
    daily: list[DailyPointDict]
    top_cities: list[MapCityDict]


class SshClientDict(TypedDict):
    client_version: str
    sessions: int


class FingerprintDict(TypedDict):
    fingerprint: str
    fingerprint_type: str | None
    sessions: int
    ips: int
    first_seen: str | None
    last_seen: str | None


class PayloadDownloadDict(TypedDict):
    """One downloaded payload (aggregated by SHA256)."""

    sha256: str
    name: str | None
    sessions: int
    machines: int
    first_seen: str | None
    last_seen: str | None
    countries: list[str]
    host: str | None


class TcpipDestinationDict(TypedDict):
    """One direct-tcpip relay target, grouped by destination network and port."""

    network: str | None
    port: int
    sessions: int
    hosts: int
    country_code: str | None
    country: str | None


class PayloadCountryRowDict(TypedDict):
    """One country's aggregated downloads for a payload detail."""

    country_code: str | None
    country: str | None
    sessions: int


class PayloadDetailDict(TypedDict):
    """Full detail for one downloaded payload (click-to-expand card)."""

    sha256: str
    name: str | None
    sessions: int
    first_seen: str | None
    last_seen: str | None
    countries: list[PayloadCountryRowDict]
