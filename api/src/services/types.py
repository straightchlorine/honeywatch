from __future__ import annotations

from typing import TypedDict


class AuthAttemptDict(TypedDict):
    id: int
    username: str
    password: str
    success: bool
    timestamp: str | None


class CommandDict(TypedDict):
    id: int
    input: str
    success: bool | None
    timestamp: str | None


class DownloadDict(TypedDict):
    id: int
    url: str | None
    outfile: str | None
    sha256: str | None
    timestamp: str | None


class SessionSummaryDict(TypedDict):
    id: str
    src_ip: str
    src_port: int
    dst_port: int
    protocol: str
    started_at: str | None
    ended_at: str | None
    auth_attempt_count: int


class SessionDetailDict(TypedDict):
    id: str
    src_ip: str
    src_port: int
    dst_ip: str | None
    dst_port: int
    protocol: str
    started_at: str | None
    ended_at: str | None
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


class TopUsernameDict(TypedDict):
    username: str
    count: int


class TopPasswordDict(TypedDict):
    password: str
    count: int


class AttacksPerDayDict(TypedDict):
    date: str
    count: int


class StatsDict(TypedDict):
    total_sessions: int
    total_auth_attempts: int
    unique_ips: int
    top_usernames: list[TopUsernameDict]
    top_passwords: list[TopPasswordDict]
    attacks_per_day: list[AttacksPerDayDict]
