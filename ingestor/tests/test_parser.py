from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.events import (
    CommandInput,
    FileDownload,
    LoginFailed,
    LoginSuccess,
    SessionClosed,
    SessionConnect,
)
from src.parser import _seen_drift, parse_event


def test_parse_session_connect(sample_connect_event: str) -> None:
    event = parse_event(sample_connect_event)
    assert isinstance(event, SessionConnect)
    assert event.session_id == "abc123"
    assert event.src_ip == "192.168.1.100"
    assert event.src_port == 54321
    assert event.dst_ip == "10.0.0.1"
    assert event.dst_port == 2222
    assert event.protocol == "ssh"
    assert event.timestamp == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    assert event.sensor == "honeypot-01"


def test_parse_login_failed(sample_login_failed: str) -> None:
    event = parse_event(sample_login_failed)
    assert isinstance(event, LoginFailed)
    assert event.session_id == "abc123"
    assert event.username == "root"
    assert event.password == "password123"
    assert event.timestamp == datetime(2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc)


def test_parse_login_success(sample_login_success: str) -> None:
    event = parse_event(sample_login_success)
    assert isinstance(event, LoginSuccess)
    assert event.session_id == "abc123"
    assert event.username == "root"
    assert event.password == "toor"
    assert event.timestamp == datetime(2024, 1, 15, 10, 30, 10, tzinfo=timezone.utc)


def test_parse_command_input(sample_command: str) -> None:
    event = parse_event(sample_command)
    assert isinstance(event, CommandInput)
    assert event.session_id == "abc123"
    assert event.input == "cat /etc/passwd"
    assert event.timestamp == datetime(2024, 1, 15, 10, 30, 15, tzinfo=timezone.utc)


def test_parse_file_download(sample_download: str) -> None:
    event = parse_event(sample_download)
    assert isinstance(event, FileDownload)
    assert event.session_id == "abc123"
    assert event.url == "http://evil.com/malware.sh"
    assert event.outfile == "/tmp/malware.sh"
    assert event.sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert event.timestamp == datetime(2024, 1, 15, 10, 30, 20, tzinfo=timezone.utc)


def test_parse_session_closed(sample_session_closed: str) -> None:
    event = parse_event(sample_session_closed)
    assert isinstance(event, SessionClosed)
    assert event.session_id == "abc123"
    assert event.timestamp == datetime(2024, 1, 15, 10, 31, 0, tzinfo=timezone.utc)


def test_parse_session_connect_missing_src_ip_rejected() -> None:
    """`sessions.src_ip` is NOT NULL; a connect missing it must fail parsing.

    Otherwise it would reach the writer as a valid `SessionConnect(src_ip=None)`,
    fail the INSERT with a NotNullViolation the writer's DataError handler
    doesn't catch, and get retried forever instead of counted as parser drift.
    """
    line = (
        '{"eventid": "cowrie.session.connect", "session": "abc123",'
        ' "dst_ip": "10.0.0.1", "dst_port": 2222, "protocol": "ssh",'
        ' "timestamp": "2024-01-15T10:30:00.000000Z", "sensor": "honeypot-01"}'
    )
    event = parse_event(line)
    assert event is None


def test_parse_unknown_event() -> None:
    line = '{"eventid": "cowrie.unknown.event", "session": "abc123"}'
    event = parse_event(line)
    assert event is None


def test_parse_malformed_json() -> None:
    event = parse_event("this is not json{{{")
    assert event is None


def test_drift_log_sanitizes_control_chars(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Attacker-crafted control chars in cowrie payload must not reach logs raw.

    Cowrie's `input` field captures attacker bytes verbatim. If an attacker
    can produce a drifted event (e.g. malformed JSON, unknown eventid), the
    raw excerpt that lands in operator logs must be defanged.
    """
    _seen_drift.clear()
    line = (
        '{"eventid":"cowrie.unknown.\\u001b[31mfake",'
        '"session":"X\\nINJECTED","timestamp":"2024-01-01T00:00:00Z"}'
    )
    with caplog.at_level("WARNING", logger="src.parser"):
        result = parse_event(line)

    assert result is None
    msg = " ".join(r.message for r in caplog.records)
    assert "\x1b" not in msg
    assert "\n" not in msg
    # Keep escaped form for operator visibility, but defang raw bytes.
    assert "\\x1b" in msg


def test_drift_log_rate_limited_per_eventid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate drift events are rate-limited to DEBUG to prevent log spam."""
    _seen_drift.clear()
    bad = '{"eventid":"cowrie.unknown.new","session":"a","timestamp":"x"}'

    with caplog.at_level("WARNING", logger="src.parser"):
        parse_event(bad)
        parse_event(bad)

    warns = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warns) == 1, "second sighting must not log at WARNING"


def test_drift_extracts_eventid_via_json_not_regex() -> None:
    """JSON-escaped quote inside eventid must not break extraction.

    A regex-based eventid pull breaks on `\\"` whereas json.loads handles it.
    """
    _seen_drift.clear()
    line = '{"eventid":"cowrie.x\\"y","session":"a","timestamp":"x"}'
    assert parse_event(line) is None
