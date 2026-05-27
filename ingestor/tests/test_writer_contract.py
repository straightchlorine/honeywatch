"""Cowrie JSON schema contract test.

Reads `tests/fixtures/cowrie_sample.jsonl` - one of each event the parser
models - and asserts each line parses, the writer-dispatched ones land in
Postgres with the expected shape, and the non-dispatched ones (client.*)
parse without error so an upstream cowrie field-rename fails CI loudly.

Regenerate the fixture by piping a recorded cowrie session into
`scripts/regen_cowrie_fixture.py`:

    docker exec honeywatch-cowrie cat /logs/cowrie.json \\
        | python scripts/regen_cowrie_fixture.py \\
        > ingestor/tests/fixtures/cowrie_sample.jsonl
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from src.events import ClientKex, ClientSize, ClientVersion, SessionClosed
from src.parser import parse_event
from src.writer import EventWriter
from tests.conftest import DbConn

_FIXTURE = Path(__file__).parent / "fixtures" / "cowrie_sample.jsonl"
_CONTRACT_SESSION_ID = "contract-sess-01"


def _lines() -> list[str]:
    raw = _FIXTURE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in raw if line.strip()]


@pytest.fixture
def populated_db(writer: EventWriter, db_connection: DbConn) -> DbConn:
    """Replay every fixture line through the production parser + writer."""
    lines = _lines()
    assert lines, "fixture is empty; regenerate via scripts/regen_cowrie_fixture.py"
    for raw in lines:
        event = parse_event(raw)
        assert event is not None, f"parser rejected fixture line: {raw[:200]}"
        writer.write_event(event)
    return db_connection


def test_session_row_written_and_closed(populated_db: DbConn) -> None:
    sessions = populated_db.execute(
        "SELECT id, src_ip, src_port, protocol, ended_at FROM sessions WHERE id = %s",
        (_CONTRACT_SESSION_ID,),
    ).fetchall()
    assert len(sessions) == 1
    session_id, src_ip, src_port, protocol, ended_at = sessions[0]
    assert session_id == _CONTRACT_SESSION_ID
    assert str(src_ip) == "203.0.113.45"
    assert src_port == 43726
    assert protocol == "ssh"
    assert ended_at is not None


def test_auth_attempts_written(populated_db: DbConn) -> None:
    auths = populated_db.execute(
        "SELECT username, password, success FROM auth_attempts "
        "WHERE session_id = %s ORDER BY timestamp",
        (_CONTRACT_SESSION_ID,),
    ).fetchall()
    assert len(auths) == 2
    # The failed-login fixture uses a password with an embedded space to
    # match the shape of real cowrie captures (e.g. "testing pass").
    assert auths[0] == ("root", "testing pass", False)
    assert auths[1] == ("root", "123456", True)


def test_command_written(populated_db: DbConn) -> None:
    commands = populated_db.execute(
        "SELECT input FROM commands WHERE session_id = %s",
        (_CONTRACT_SESSION_ID,),
    ).fetchall()
    assert commands == [("uname -a",)]


def test_download_written(populated_db: DbConn) -> None:
    downloads = populated_db.execute(
        "SELECT url, outfile, sha256 FROM downloads WHERE session_id = %s",
        (_CONTRACT_SESSION_ID,),
    ).fetchall()
    assert len(downloads) == 1
    url, outfile, sha256 = downloads[0]
    assert url == "http://1.2.3.4/payload.sh"
    assert outfile == "var/lib/cowrie/downloads/abc123"
    assert sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_session_closed_duration_coerces_to_float() -> None:
    """Cowrie emits `duration` as a JSON string ("81.1"), pydantic lax-coerces."""
    for raw in _lines():
        event = parse_event(raw)
        if isinstance(event, SessionClosed):
            assert isinstance(event.duration, float)
            assert event.duration > 0
            return
    pytest.fail("fixture has no cowrie.session.closed event")


def test_non_dispatched_client_events_parse() -> None:
    """`client.version`/`kex`/`size` aren't written but must still parse.

    A field rename upstream would silently break enrichment (we use
    `hassh` for fingerprinting in downstream Grafana panels); the
    contract test catches it here at PR time instead of in production.
    """
    parsed = [parse_event(line) for line in _lines()]
    kinds = {type(event) for event in parsed if event is not None}
    assert ClientVersion in kinds
    assert ClientKex in kinds
    assert ClientSize in kinds
    # Sanity-check the specific fields downstream Grafana panels read.
    kex = next(e for e in parsed if isinstance(e, ClientKex))
    assert cast(str, kex.hassh) == "eeca2460550b9ded084ecf2f70a75356"
