from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionConnect:
    session_id: str
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: str
    timestamp: datetime
    sensor: str | None


@dataclass(frozen=True)
class LoginAttempt:
    session_id: str
    username: str
    password: str
    success: bool
    timestamp: datetime


@dataclass(frozen=True)
class CommandInput:
    session_id: str
    input: str
    timestamp: datetime


@dataclass(frozen=True)
class FileDownload:
    session_id: str
    url: str | None
    outfile: str | None
    sha256: str | None
    timestamp: datetime


@dataclass(frozen=True)
class SessionClosed:
    session_id: str
    timestamp: datetime


type CowrieEvent = (
    SessionConnect | LoginAttempt | CommandInput | FileDownload | SessionClosed
)


def _parse_timestamp(raw: str) -> datetime:
    """Parse a cowrie ISO 8601 timestamp into a timezone-aware datetime."""
    ts = datetime.fromisoformat(raw)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def parse_event(line: str) -> CowrieEvent | None:
    """Parse a single cowrie JSON log line into a typed event.

    Returns None for unhandled event types or malformed JSON.
    """
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Malformed JSON line: %s", line[:200])
        return None

    event_id = data.get("eventid")
    if event_id is None:
        return None

    try:
        match event_id:
            case "cowrie.session.connect":
                return SessionConnect(
                    session_id=data["session"],
                    src_ip=data["src_ip"],
                    src_port=data["src_port"],
                    dst_ip=data["dst_ip"],
                    dst_port=data["dst_port"],
                    protocol=data["protocol"],
                    timestamp=_parse_timestamp(data["timestamp"]),
                    sensor=data.get("sensor"),
                )
            case "cowrie.login.success":
                return LoginAttempt(
                    session_id=data["session"],
                    username=data["username"],
                    password=data["password"],
                    success=True,
                    timestamp=_parse_timestamp(data["timestamp"]),
                )
            case "cowrie.login.failed":
                return LoginAttempt(
                    session_id=data["session"],
                    username=data["username"],
                    password=data["password"],
                    success=False,
                    timestamp=_parse_timestamp(data["timestamp"]),
                )
            case "cowrie.command.input":
                return CommandInput(
                    session_id=data["session"],
                    input=data["input"],
                    timestamp=_parse_timestamp(data["timestamp"]),
                )
            case "cowrie.session.file_download":
                return FileDownload(
                    session_id=data["session"],
                    url=data.get("url"),
                    outfile=data.get("outfile"),
                    sha256=data.get("shasum"),
                    timestamp=_parse_timestamp(data["timestamp"]),
                )
            case "cowrie.session.closed":
                return SessionClosed(
                    session_id=data["session"],
                    timestamp=_parse_timestamp(data["timestamp"]),
                )
            case _:
                return None
    except (KeyError, ValueError) as exc:
        logger.warning("Failed to parse event %s: %s", event_id, exc)
        return None
