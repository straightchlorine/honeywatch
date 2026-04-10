from __future__ import annotations

from datetime import datetime, timezone

from src.parser import (
    CommandInput,
    FileDownload,
    LoginAttempt,
    SessionClosed,
    SessionConnect,
    parse_event,
)


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
    assert isinstance(event, LoginAttempt)
    assert event.session_id == "abc123"
    assert event.username == "root"
    assert event.password == "password123"
    assert event.success is False
    assert event.timestamp == datetime(2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc)


def test_parse_login_success(sample_login_success: str) -> None:
    event = parse_event(sample_login_success)
    assert isinstance(event, LoginAttempt)
    assert event.session_id == "abc123"
    assert event.username == "root"
    assert event.password == "toor"
    assert event.success is True
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


def test_parse_unknown_event() -> None:
    line = '{"eventid": "cowrie.unknown.event", "session": "abc123"}'
    event = parse_event(line)
    assert event is None


def test_parse_malformed_json() -> None:
    event = parse_event("this is not json{{{")
    assert event is None
