from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import psycopg
import pytest

from src.parser import (
    CommandInput,
    FileDownload,
    LoginAttempt,
    SessionClosed,
    SessionConnect,
)
from src.writer import EventWriter


@pytest.fixture
def writer(db_url: str) -> Generator[EventWriter]:
    w = EventWriter(db_url)
    yield w
    w.close()


def _connect_event() -> SessionConnect:
    return SessionConnect(
        session_id="sess-001",
        src_ip="192.168.1.100",
        src_port=54321,
        dst_ip="10.0.0.1",
        dst_port=2222,
        protocol="ssh",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        sensor="honeypot-01",
    )


def test_write_session_connect(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    event = _connect_event()
    writer.write_event(event)

    row = db_connection.execute(
        "SELECT id, src_ip, src_port, dst_ip, dst_port,"
        " protocol, sensor FROM sessions WHERE id = %s",
        (event.session_id,),
    ).fetchone()

    assert row is not None
    assert row[0] == "sess-001"
    assert str(row[1]) == "192.168.1.100"
    assert row[2] == 54321
    assert str(row[3]) == "10.0.0.1"
    assert row[4] == 2222
    assert row[5] == "ssh"
    assert row[6] == "honeypot-01"


def test_write_login_attempt(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    writer.write_event(_connect_event())

    event = LoginAttempt(
        session_id="sess-001",
        username="root",
        password="password123",
        success=False,
        timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc),
    )
    writer.write_event(event)

    row = db_connection.execute(
        "SELECT session_id, username, password, success"
        " FROM auth_attempts WHERE session_id = %s",
        (event.session_id,),
    ).fetchone()

    assert row is not None
    assert row[0] == "sess-001"
    assert row[1] == "root"
    assert row[2] == "password123"
    assert row[3] is False


def test_write_command(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    writer.write_event(_connect_event())

    event = CommandInput(
        session_id="sess-001",
        input="cat /etc/passwd",
        timestamp=datetime(2024, 1, 15, 10, 30, 15, tzinfo=timezone.utc),
    )
    writer.write_event(event)

    row = db_connection.execute(
        "SELECT session_id, input, success FROM commands WHERE session_id = %s",
        (event.session_id,),
    ).fetchone()

    assert row is not None
    assert row[0] == "sess-001"
    assert row[1] == "cat /etc/passwd"
    assert row[2] is True


def test_write_download(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    writer.write_event(_connect_event())

    event = FileDownload(
        session_id="sess-001",
        url="http://evil.com/malware.sh",
        outfile="/tmp/malware.sh",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        timestamp=datetime(2024, 1, 15, 10, 30, 20, tzinfo=timezone.utc),
    )
    writer.write_event(event)

    row = db_connection.execute(
        "SELECT session_id, url, outfile, sha256 FROM downloads WHERE session_id = %s",
        (event.session_id,),
    ).fetchone()

    assert row is not None
    assert row[0] == "sess-001"
    assert row[1] == "http://evil.com/malware.sh"
    assert row[2] == "/tmp/malware.sh"
    assert row[3] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_write_session_closed(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    writer.write_event(_connect_event())

    closed = SessionClosed(
        session_id="sess-001",
        timestamp=datetime(2024, 1, 15, 10, 31, 0, tzinfo=timezone.utc),
    )
    writer.write_event(closed)

    row = db_connection.execute(
        "SELECT ended_at FROM sessions WHERE id = %s",
        ("sess-001",),
    ).fetchone()

    assert row is not None
    assert row[0] == datetime(2024, 1, 15, 10, 31, 0, tzinfo=timezone.utc)


def test_duplicate_session_ignored(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    event = _connect_event()
    writer.write_event(event)
    # Writing the same session again should not raise an error
    writer.write_event(event)

    count = db_connection.execute(
        "SELECT count(*) FROM sessions WHERE id = %s",
        (event.session_id,),
    ).fetchone()

    assert count is not None
    assert count[0] == 1
