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

import re
from pathlib import Path
from typing import cast

import pytest

from src import writer as writer_module
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


def test_ssh_client_written(populated_db: DbConn) -> None:
    """client.version + client.kex are merged into one ssh_clients row."""
    row = populated_db.execute(
        "SELECT client_version, hassh FROM ssh_clients WHERE session_id = %s",
        (_CONTRACT_SESSION_ID,),
    ).fetchone()
    assert row is not None
    client_version, hassh = row
    assert isinstance(client_version, str) and client_version.startswith("SSH-2.0")
    assert hassh == "eeca2460550b9ded084ecf2f70a75356"


def test_session_closed_duration_coerces_to_float() -> None:
    """Cowrie emits `duration` as a JSON string ("81.1"), pydantic lax-coerces."""
    for raw in _lines():
        event = parse_event(raw)
        if isinstance(event, SessionClosed):
            assert isinstance(event.duration, float)
            assert event.duration > 0
            return
    pytest.fail("fixture has no cowrie.session.closed event")


# (table, [SQL fragments the writer issues against this table])
_WRITER_TABLE_BINDINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "sessions",
        (writer_module._INSERT_SESSION, writer_module._UPDATE_SESSION_CLOSED),
    ),
    ("auth_attempts", (writer_module._INSERT_AUTH_ATTEMPT,)),
    ("commands", (writer_module._INSERT_COMMAND,)),
    ("downloads", (writer_module._INSERT_DOWNLOAD,)),
    ("geo_locations", (writer_module._UPSERT_GEO,)),
    (
        "ssh_clients",
        (
            writer_module._UPSERT_SSH_CLIENT_VERSION,
            writer_module._UPSERT_SSH_CLIENT_KEX,
        ),
    ),
    ("client_fingerprints", (writer_module._INSERT_CLIENT_FINGERPRINT,)),
    ("direct_tcpip_requests", (writer_module._INSERT_DIRECT_TCPIP,)),
)

_INSERT_COLS_RE = re.compile(
    r"INSERT\s+INTO\s+\w+\s*\(([^)]+)\)", re.IGNORECASE | re.DOTALL
)
_UPDATE_SET_RE = re.compile(
    r"UPDATE\s+\w+\s+SET\s+(.+?)\s+WHERE", re.IGNORECASE | re.DOTALL
)
_UPDATE_WHERE_RE = re.compile(r"WHERE\s+(\w+)\s*=", re.IGNORECASE)
_ASSIGN_COL_RE = re.compile(r"(\w+)\s*=")


def _columns_referenced(sql: str) -> set[str]:
    """Best-effort column extraction from the writer's SQL strings."""
    cols: set[str] = set()
    match = _INSERT_COLS_RE.search(sql)
    if match:
        for raw in match.group(1).split(","):
            cols.add(raw.strip().strip('"'))
    match = _UPDATE_SET_RE.search(sql)
    if match:
        for assignment in match.group(1).split(","):
            assign = _ASSIGN_COL_RE.match(assignment.strip())
            if assign:
                cols.add(assign.group(1).strip('"'))
    where = _UPDATE_WHERE_RE.search(sql)
    if where:
        cols.add(where.group(1).strip('"'))
    return cols


@pytest.mark.parametrize("table,sql_fragments", _WRITER_TABLE_BINDINGS)
def test_writer_columns_match_table_schema(
    db_connection: DbConn, table: str, sql_fragments: tuple[str, ...]
) -> None:
    """Writer columns ⊆ schema columns; NOT-NULL-no-default columns ⊆ writer columns."""
    writer_cols: set[str] = set()
    for fragment in sql_fragments:
        writer_cols |= _columns_referenced(fragment)
    assert writer_cols, f"failed to extract any columns for {table}"

    rows = db_connection.execute(
        "SELECT column_name, is_nullable, column_default "
        "FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s",
        (table,),
    ).fetchall()
    assert rows, f"table {table} not present in test DB"
    table_cols = {r[0] for r in rows}
    required_cols = {r[0] for r in rows if r[1] == "NO" and r[2] is None}

    unknown = writer_cols - table_cols
    assert not unknown, (
        f"{table}: writer references columns absent from the schema: {unknown}. "
        f"Did a migration drop a column the writer still uses?"
    )

    missing = required_cols - writer_cols
    assert not missing, (
        f"{table}: writer omits NOT NULL no-default columns: {missing}. "
        f"Did a migration add a NOT NULL column without updating writer.py?"
    )


# Each entry: (table, column, writer-side `_LEN_*` constant).
# Catches drift between writer caps and DB VARCHAR(N) caps.
_WRITER_LENGTH_CAPS: tuple[tuple[str, str, int], ...] = (
    ("sessions", "id", writer_module._LEN_SESSION_ID),
    ("sessions", "protocol", writer_module._LEN_PROTOCOL),
    ("sessions", "sensor", writer_module._LEN_SENSOR),
    ("auth_attempts", "session_id", writer_module._LEN_SESSION_ID),
    ("auth_attempts", "username", writer_module._LEN_USERNAME),
    ("auth_attempts", "password", writer_module._LEN_PASSWORD),
    ("commands", "session_id", writer_module._LEN_SESSION_ID),
    ("commands", "input", writer_module._LEN_COMMAND_INPUT),
    ("downloads", "session_id", writer_module._LEN_SESSION_ID),
    ("downloads", "url", writer_module._LEN_URL),
    ("downloads", "outfile", writer_module._LEN_OUTFILE),
    ("downloads", "sha256", writer_module._LEN_SHA256),
    ("geo_locations", "country_code", writer_module._LEN_COUNTRY_CODE),
    ("geo_locations", "country", writer_module._LEN_COUNTRY),
    ("geo_locations", "city", writer_module._LEN_CITY),
    ("geo_locations", "as_org", writer_module._LEN_AS_ORG),
    ("ssh_clients", "session_id", writer_module._LEN_SESSION_ID),
    ("ssh_clients", "client_version", writer_module._LEN_CLIENT_VERSION),
    ("ssh_clients", "hassh", writer_module._LEN_HASSH),
    ("ssh_clients", "hassh_algorithms", writer_module._LEN_HASSH_ALGORITHMS),
    ("client_fingerprints", "session_id", writer_module._LEN_SESSION_ID),
    ("client_fingerprints", "username", writer_module._LEN_USERNAME),
    ("client_fingerprints", "fingerprint", writer_module._LEN_FINGERPRINT),
    ("client_fingerprints", "fingerprint_type", writer_module._LEN_FINGERPRINT_TYPE),
    ("direct_tcpip_requests", "session_id", writer_module._LEN_SESSION_ID),
    ("direct_tcpip_requests", "dst_ip", writer_module._LEN_HOST),
    ("direct_tcpip_requests", "src_ip", writer_module._LEN_HOST),
)


@pytest.mark.parametrize("table,column,writer_cap", _WRITER_LENGTH_CAPS)
def test_writer_length_caps_match_schema(
    db_connection: DbConn, table: str, column: str, writer_cap: int
) -> None:
    """Writer `_LEN_*` must equal `information_schema.character_maximum_length`."""
    row = db_connection.execute(
        "SELECT character_maximum_length FROM information_schema.columns "
        "WHERE table_schema = current_schema() "
        "AND table_name = %s AND column_name = %s",
        (table, column),
    ).fetchone()
    assert row is not None, f"{table}.{column} not present in test DB"
    db_cap = row[0]
    assert db_cap == writer_cap, (
        f"{table}.{column}: writer caps at {writer_cap}, DB caps at {db_cap}. "
        f"Update writer._LEN_* and migration in lockstep with the model."
    )


def test_non_dispatched_client_events_parse() -> None:
    """All client.* events must keep parsing as cowrie's schema evolves.

    `client.version`/`kex` are now persisted (see `test_ssh_client_written`);
    `client.size` is intentionally not. A field rename upstream would silently
    break HASSH capture, so the contract test catches it at PR time instead of
    in production.
    """
    parsed = [parse_event(line) for line in _lines()]
    kinds = {type(event) for event in parsed if event is not None}
    assert ClientVersion in kinds
    assert ClientKex in kinds
    assert ClientSize in kinds
    # Sanity-check the specific fields downstream Grafana panels read.
    kex = next(e for e in parsed if isinstance(e, ClientKex))
    assert cast(str, kex.hassh) == "eeca2460550b9ded084ecf2f70a75356"
