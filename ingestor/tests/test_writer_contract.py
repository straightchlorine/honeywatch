"""Cowrie JSON schema contract test.

Reads tests/fixtures/cowrie_sample.jsonl - a recorded slice covering
every event type the writer dispatches on - parses each line through
the production parser, writes each parsed event through the production
writer, and asserts the expected row counts landed in Postgres.

When cowrie's upstream image bumps and changes the shape of any event
we model (added required field, renamed key, type change), the parser
will reject the affected line and this test will fail loudly in CI.
Drift becomes a PR-blocking signal instead of a silent prod regression
that nobody notices until the dashboard goes quiet.

Regenerate the fixture by capturing fresh cowrie output:

    just dev   # ingestor runs with DROP_LOOPBACK=0
    just attack root  # authenticate with userdb password (e.g. 123456)
    # run commands + a wget in the cowrie shell, then exit
    docker exec honeywatch-ingestor cat /logs/cowrie.json \\
        | tail -n 40 > ingestor/tests/fixtures/cowrie_sample.jsonl
    # trim to one of each handled eventid, share one `session` id

The fixture must contain exactly one of each event type the writer's
match statement in writer.py handles - the assertions below assume
that shape.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest

from src.parser import parse_event
from src.writer import EventWriter

_FIXTURE = Path(__file__).parent / "fixtures" / "cowrie_sample.jsonl"


@pytest.fixture
def writer(db_url: str) -> Generator[EventWriter]:
    with EventWriter(db_url) as w:
        yield w


def test_cowrie_sample_round_trip(
    writer: EventWriter,
    db_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Every line in the captured cowrie sample parses and persists."""
    lines = [
        line.strip()
        for line in _FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines, "fixture is empty; regenerate per docstring"

    for raw in lines:
        event = parse_event(raw)
        assert event is not None, f"parser rejected fixture line: {raw[:200]}"
        writer.write_event(event)

    # One session row from cowrie.session.connect, then session.closed
    # updates ended_at on the same row (no extra row inserted).
    sessions = db_connection.execute(
        "SELECT id, src_ip, src_port, protocol, ended_at FROM sessions WHERE id = %s",
        ("contract-sess-01",),
    ).fetchall()
    assert len(sessions) == 1
    session_id, src_ip, src_port, protocol, ended_at = sessions[0]
    assert session_id == "contract-sess-01"
    assert str(src_ip) == "203.0.113.45"
    assert src_port == 43726
    assert protocol == "ssh"
    assert ended_at is not None, "session.closed must populate ended_at"

    # One failed + one successful login attempt against the same session.
    auths = db_connection.execute(
        "SELECT username, password, success FROM auth_attempts "
        "WHERE session_id = %s ORDER BY timestamp",
        ("contract-sess-01",),
    ).fetchall()
    assert len(auths) == 2
    assert auths[0] == ("root", "wrong-pw", False)
    assert auths[1] == ("root", "123456", True)

    # One command.input line.
    commands = db_connection.execute(
        "SELECT input FROM commands WHERE session_id = %s",
        ("contract-sess-01",),
    ).fetchall()
    assert commands == [("uname -a",)]

    # One file_download line.
    downloads = db_connection.execute(
        "SELECT url, outfile, sha256 FROM downloads WHERE session_id = %s",
        ("contract-sess-01",),
    ).fetchall()
    assert len(downloads) == 1
    url, outfile, sha256 = downloads[0]
    assert url == "http://1.2.3.4/payload.sh"
    assert outfile == "var/lib/cowrie/downloads/abc123"
    assert sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
