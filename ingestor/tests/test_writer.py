from __future__ import annotations

from datetime import datetime, timezone
from typing import LiteralString
from unittest.mock import patch

import pytest

from src import writer as writer_module
from src.events import (
    ClientFingerprint,
    ClientKex,
    ClientVersion,
    CommandInput,
    CowrieEvent,
    DirectTcpipRequest,
    FileDownload,
    LoginFailed,
    LoginSuccess,
    SessionClosed,
    SessionConnect,
)
from src.writer import EventWriter
from tests.conftest import DbConn

# Shared event timestamp for the client/kex/fingerprint/direct-tcpip tests below.
_TS = datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc)


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
    db_connection: DbConn,
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
    db_connection: DbConn,
) -> None:
    writer.write_event(_connect_event())

    event = LoginFailed(
        session_id="sess-001",
        username="root",
        password="password123",
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
    db_connection: DbConn,
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
    db_connection: DbConn,
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
    db_connection: DbConn,
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


def test_write_client_version_then_kex_upserts_one_row(
    writer: EventWriter,
    db_connection: DbConn,
) -> None:
    """version + kex are separate events; each upserts ssh_clients in place."""
    writer.write_event(_connect_event())
    writer.write_event(
        ClientVersion(
            session_id="sess-001",
            version="SSH-2.0-libssh2_1.9.0",
            timestamp=datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc),
        )
    )
    writer.write_event(
        ClientKex(
            session_id="sess-001",
            hassh="eeca2460550b9ded084ecf2f70a75356",
            hasshAlgorithms="curve25519-sha256;aes128-ctr;hmac-sha2-256;none",
            kexAlgs=["curve25519-sha256", "ecdh-sha2-nistp256"],
            keyAlgs=["ssh-ed25519"],
            encCS=["aes128-ctr", "aes256-ctr"],
            macCS=["hmac-sha2-256"],
            compCS=["none"],
            timestamp=datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc),
        )
    )

    row = db_connection.execute(
        "SELECT client_version, hassh, kex_algorithms, encryption_algorithms"
        " FROM ssh_clients WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    assert row[0] == "SSH-2.0-libssh2_1.9.0"  # preserved from the version event
    assert row[1] == "eeca2460550b9ded084ecf2f70a75356"  # set by the kex event
    assert row[2] == "curve25519-sha256,ecdh-sha2-nistp256"
    assert row[3] == "aes128-ctr,aes256-ctr"

    count = db_connection.execute(
        "SELECT count(*) FROM ssh_clients WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert count is not None
    assert count[0] == 1  # upsert merged, did not create a second row


def test_write_client_fingerprint(
    writer: EventWriter,
    db_connection: DbConn,
) -> None:
    writer.write_event(_connect_event())
    writer.write_event(
        ClientFingerprint(
            session_id="sess-001",
            username="root",
            fingerprint="SHA256:n0tArealKeyFingerprintAAAAAAAAAAAAAAAAAAAAAA",
            type="ssh-ed25519",
            timestamp=datetime(2024, 1, 15, 10, 30, 3, tzinfo=timezone.utc),
        )
    )

    row = db_connection.execute(
        "SELECT username, fingerprint, fingerprint_type"
        " FROM client_fingerprints WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    assert row[0] == "root"
    assert row[1] == "SHA256:n0tArealKeyFingerprintAAAAAAAAAAAAAAAAAAAAAA"
    assert row[2] == "ssh-ed25519"


def test_write_direct_tcpip_request(
    writer: EventWriter,
    db_connection: DbConn,
) -> None:
    writer.write_event(_connect_event())
    writer.write_event(
        DirectTcpipRequest(
            session_id="sess-001",
            dst_ip="smtp.example.com",
            dst_port=25,
            src_ip="127.0.0.1",
            src_port=40000,
            timestamp=datetime(2024, 1, 15, 10, 30, 4, tzinfo=timezone.utc),
        )
    )

    row = db_connection.execute(
        "SELECT dst_ip, dst_port, src_ip, src_port"
        " FROM direct_tcpip_requests WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    assert row[0] == "smtp.example.com"
    assert row[1] == 25
    assert row[2] == "127.0.0.1"
    assert row[3] == 40000


@pytest.mark.parametrize(
    ("drop_loopback", "expected"),
    [(True, 0), (False, 1)],
)
def test_loopback_session_gated_by_flag(
    db_url: str,
    db_connection: DbConn,
    drop_loopback: bool,
    expected: int,
) -> None:
    """Cowrie's docker healthcheck dials 127.0.0.1:2222.

    Production drops them (`drop_loopback=True`); dev keeps them so an
    operator's `just attack` from the host appears in the session list.
    """
    event = SessionConnect(
        session_id=f"sess-loopback-{drop_loopback}",
        src_ip="127.0.0.1",
        src_port=54321,
        dst_ip="127.0.0.1",
        dst_port=2222,
        protocol="ssh",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        sensor="honeypot-01",
    )
    with EventWriter(db_url, drop_loopback=drop_loopback) as w:
        w.write_event(event)

    count = db_connection.execute(
        "SELECT count(*) FROM sessions WHERE id = %s",
        (event.session_id,),
    ).fetchone()

    assert count is not None
    assert count[0] == expected


def test_duplicate_session_ignored(
    writer: EventWriter,
    db_connection: DbConn,
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


def test_geo_enrichment_populates_geo_locations(
    writer: EventWriter,
    db_connection: DbConn,
) -> None:
    # Skip when mmdb files are not present (CI without secrets, fresh clone).
    from src.geoip import _ASN_PATH, _CITY_PATH

    if not _CITY_PATH.exists() or not _ASN_PATH.exists():
        pytest.skip("GeoLite2 mmdb files not available locally")

    event = SessionConnect(
        session_id="sess-geo-001",
        src_ip="8.8.8.8",  # Google DNS, stable: US + ASN 15169
        src_port=54321,
        dst_ip="10.0.0.1",
        dst_port=2222,
        protocol="ssh",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        sensor="honeypot-01",
    )
    writer.write_event(event)

    row = db_connection.execute(
        "SELECT country_code, asn, as_org FROM geo_locations WHERE ip = %s",
        (event.src_ip,),
    ).fetchone()

    assert row is not None
    assert row[0] == "US"
    assert row[1] == 15169
    as_org = row[2]
    assert isinstance(as_org, str)
    assert "Google" in as_org


def test_session_closed_orphan_logs_and_skips(
    writer: EventWriter,
    db_connection: DbConn,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SessionClosed with no prior connect must be a silent no-op + log."""
    closed = SessionClosed(
        session_id="sess-orphan",
        timestamp=datetime(2024, 1, 15, 10, 31, 0, tzinfo=timezone.utc),
    )
    with caplog.at_level("INFO", logger="src.writer"):
        writer.write_event(closed)

    count = db_connection.execute(
        "SELECT count(*) FROM sessions WHERE id = %s",
        ("sess-orphan",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any("orphan session_closed event" in r.message for r in caplog.records)


def test_login_attempt_orphan_caught(
    writer: EventWriter,
    db_connection: DbConn,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LoginFailed for an unknown session must catch FK violation, not raise.

    Happens at startup mid-stream: tail seeks to EOF, missing the connect.
    Without the FK catch this would crash the retry loop.
    """
    event = LoginFailed(
        session_id="sess-orphan-auth",
        username="root",
        password="x",
        timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc),
    )
    with caplog.at_level("INFO", logger="src.writer"):
        writer.write_event(event)

    count = db_connection.execute(
        "SELECT count(*) FROM auth_attempts WHERE session_id = %s",
        ("sess-orphan-auth",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any("orphan auth event" in r.message for r in caplog.records)


def test_login_success_orphan_caught(
    writer: EventWriter,
    db_connection: DbConn,
) -> None:
    """LoginSuccess orphan path uses the same catch."""
    event = LoginSuccess(
        session_id="sess-orphan-auth-2",
        username="root",
        password="x",
        timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc),
    )
    writer.write_event(event)
    count = db_connection.execute(
        "SELECT count(*) FROM auth_attempts WHERE session_id = %s",
        ("sess-orphan-auth-2",),
    ).fetchone()
    assert count is not None and count[0] == 0


def test_command_orphan_caught(writer: EventWriter, db_connection: DbConn) -> None:
    event = CommandInput(
        session_id="sess-orphan-cmd",
        input="id",
        timestamp=datetime(2024, 1, 15, 10, 30, 15, tzinfo=timezone.utc),
    )
    writer.write_event(event)
    count = db_connection.execute(
        "SELECT count(*) FROM commands WHERE session_id = %s",
        ("sess-orphan-cmd",),
    ).fetchone()
    assert count is not None and count[0] == 0


def test_download_orphan_caught(writer: EventWriter, db_connection: DbConn) -> None:
    event = FileDownload(
        session_id="sess-orphan-dl",
        url="http://x",
        outfile="/tmp/x",
        sha256="0" * 64,
        timestamp=datetime(2024, 1, 15, 10, 30, 20, tzinfo=timezone.utc),
    )
    writer.write_event(event)
    count = db_connection.execute(
        "SELECT count(*) FROM downloads WHERE session_id = %s",
        ("sess-orphan-dl",),
    ).fetchone()
    assert count is not None and count[0] == 0


def test_geo_failure_preserves_session(
    writer: EventWriter,
    db_connection: DbConn,
) -> None:
    """Geo upsert failure must not roll back the session row.

    Split-tx is load-bearing: an attack record is more valuable than its
    enrichment. Simulates a geo write blowing up by monkeypatching the
    geoip_lookup to return a fake hit and the geo SQL to raise.
    """
    from src import writer as writer_module
    from src.geoip import GeoData

    fake_geo = GeoData(
        country_code="US",
        country="United States",
        city="Test",
        latitude=0.0,
        longitude=0.0,
        asn=0,
        as_org="Test",
    )

    with patch.object(writer_module, "geoip_lookup", return_value=fake_geo):
        with patch(
            "src.writer._UPSERT_GEO",
            "INSERT INTO geo_locations (this_column_does_not_exist) VALUES (1)",
        ):
            event = SessionConnect(
                session_id="sess-geo-fail",
                src_ip="203.0.113.7",
                src_port=44444,
                dst_ip="10.0.0.1",
                dst_port=2222,
                protocol="ssh",
                timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                sensor="honeypot-01",
            )
            writer.write_event(event)

    # Session row preserved despite geo upsert failure.
    count = db_connection.execute(
        "SELECT count(*) FROM sessions WHERE id = %s",
        ("sess-geo-fail",),
    ).fetchone()
    assert count is not None and count[0] == 1


def test_pool_check_not_called_per_event(
    writer: EventWriter, db_connection: DbConn
) -> None:
    """Regression guard: per-event `pool.check()` was a hot-path tax.

    The new design relies on `ConnectionPool(check=...)` running on
    checkout, not on every write_event call.
    """
    with patch.object(writer.pool, "check") as mock_check:
        writer.write_event(_connect_event())
    mock_check.assert_not_called()


# --- New-event orphan paths (FK violation -> log + skip, never crash) ---


def test_client_version_orphan_caught(
    writer: EventWriter, db_connection: DbConn, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="src.writer"):
        writer.write_event(
            ClientVersion(
                session_id="sess-orphan-cv", version="SSH-2.0-X", timestamp=_TS
            )
        )
    count = db_connection.execute(
        "SELECT count(*) FROM ssh_clients WHERE session_id = %s",
        ("sess-orphan-cv",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any("orphan client_version event" in r.message for r in caplog.records)


def test_client_kex_orphan_caught(
    writer: EventWriter, db_connection: DbConn, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="src.writer"):
        writer.write_event(
            ClientKex(session_id="sess-orphan-kex", hassh="x", timestamp=_TS)
        )
    count = db_connection.execute(
        "SELECT count(*) FROM ssh_clients WHERE session_id = %s",
        ("sess-orphan-kex",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any("orphan client_kex event" in r.message for r in caplog.records)


def test_client_fingerprint_orphan_caught(
    writer: EventWriter, db_connection: DbConn, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="src.writer"):
        writer.write_event(
            ClientFingerprint(
                session_id="sess-orphan-fp",
                fingerprint="SHA256:x",
                type="ssh-rsa",
                timestamp=_TS,
            )
        )
    count = db_connection.execute(
        "SELECT count(*) FROM client_fingerprints WHERE session_id = %s",
        ("sess-orphan-fp",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any("orphan client_fingerprint event" in r.message for r in caplog.records)


def test_direct_tcpip_orphan_caught(
    writer: EventWriter, db_connection: DbConn, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="src.writer"):
        writer.write_event(
            DirectTcpipRequest(
                session_id="sess-orphan-dt",
                dst_ip="10.0.0.1",
                dst_port=25,
                timestamp=_TS,
            )
        )
    count = db_connection.execute(
        "SELECT count(*) FROM direct_tcpip_requests WHERE session_id = %s",
        ("sess-orphan-dt",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any("orphan direct_tcpip event" in r.message for r in caplog.records)


# --- DataError poison-pill path (drop + meter, never retry-loop) ---


def test_direct_tcpip_dst_port_overflow_dropped(
    writer: EventWriter, db_connection: DbConn, caplog: pytest.LogCaptureFixture
) -> None:
    """A dst_port beyond INT4 range hits Postgres DataError and is dropped.

    Pydantic accepts the unbounded int; the INTEGER column rejects it. The
    handler must drop (log SQLSTATE) rather than crash or retry-loop. Parent
    session exists, so this is a DataError, not an FK orphan.
    """
    writer.write_event(_connect_event())
    with caplog.at_level("WARNING", logger="src.writer"):
        writer.write_event(
            DirectTcpipRequest(
                session_id="sess-001",
                dst_ip="10.0.0.9",
                dst_port=2**31,  # > INT4 max (2147483647)
                timestamp=_TS,
            )
        )
    count = db_connection.execute(
        "SELECT count(*) FROM direct_tcpip_requests WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert count is not None and count[0] == 0
    assert any(
        "dropping malformed direct_tcpip event" in r.message
        and "sqlstate=" in r.message
        for r in caplog.records
    )


# --- Attacker-string length clamps (truncate before INSERT) ---


_CAP_CASES = [
    pytest.param(
        ClientVersion(session_id="sess-001", version="A" * 600, timestamp=_TS),
        "SELECT client_version FROM ssh_clients WHERE session_id = %s",
        writer_module._LEN_CLIENT_VERSION,
        id="client_version",
    ),
    pytest.param(
        ClientKex(session_id="sess-001", hassh="A" * 600, timestamp=_TS),
        "SELECT hassh FROM ssh_clients WHERE session_id = %s",
        writer_module._LEN_HASSH,
        id="hassh",
    ),
    pytest.param(
        ClientFingerprint(
            session_id="sess-001", fingerprint="A" * 600, type="ssh-rsa", timestamp=_TS
        ),
        "SELECT fingerprint FROM client_fingerprints WHERE session_id = %s",
        writer_module._LEN_FINGERPRINT,
        id="fingerprint",
    ),
    pytest.param(
        DirectTcpipRequest(
            session_id="sess-001", dst_ip="A" * 600, dst_port=25, timestamp=_TS
        ),
        "SELECT dst_ip FROM direct_tcpip_requests WHERE session_id = %s",
        writer_module._LEN_HOST,
        id="dst_ip",
    ),
]


@pytest.mark.parametrize(("event", "query", "cap"), _CAP_CASES)
def test_attacker_strings_clamped_to_cap(
    writer: EventWriter,
    db_connection: DbConn,
    event: CowrieEvent,
    query: LiteralString,
    cap: int,
) -> None:
    """Over-cap attacker strings are truncated to the column width, not dropped."""
    writer.write_event(_connect_event())
    writer.write_event(event)
    row = db_connection.execute(query, ("sess-001",)).fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, str)
    assert len(value) == cap


def test_kex_algorithm_lists_clamped(
    writer: EventWriter, db_connection: DbConn
) -> None:
    """Attacker-controlled KEXINIT name-lists are capped before the Text column."""
    writer.write_event(_connect_event())
    writer.write_event(
        ClientKex(
            session_id="sess-001", hassh="abc", kexAlgs=["x" * 5000], timestamp=_TS
        )
    )
    row = db_connection.execute(
        "SELECT kex_algorithms FROM ssh_clients WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, str)
    assert len(value) == writer_module._LEN_ALGORITHMS


# --- ssh_clients dual-event upsert: order-independent, no clobber ---


def test_kex_then_version_upserts_one_row(
    writer: EventWriter, db_connection: DbConn
) -> None:
    """Reverse arrival (kex first) still merges into one row without clobbering."""
    writer.write_event(_connect_event())
    writer.write_event(
        ClientKex(
            session_id="sess-001",
            hassh="deadbeef",
            kexAlgs=["curve25519-sha256"],
            timestamp=_TS,
        )
    )
    writer.write_event(
        ClientVersion(
            session_id="sess-001", version="SSH-2.0-OpenSSH_9.9", timestamp=_TS
        )
    )
    row = db_connection.execute(
        "SELECT client_version, hassh, kex_algorithms FROM ssh_clients "
        "WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    assert row[0] == "SSH-2.0-OpenSSH_9.9"  # version not clobbered by the kex upsert
    assert row[1] == "deadbeef"  # hassh preserved from the kex event
    assert row[2] == "curve25519-sha256"
    count = db_connection.execute(
        "SELECT count(*) FROM ssh_clients WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert count is not None and count[0] == 1


def test_client_version_only_row(writer: EventWriter, db_connection: DbConn) -> None:
    """version arriving alone leaves the kex columns NULL."""
    writer.write_event(_connect_event())
    writer.write_event(
        ClientVersion(session_id="sess-001", version="SSH-2.0-X", timestamp=_TS)
    )
    row = db_connection.execute(
        "SELECT client_version, hassh FROM ssh_clients WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    assert row[0] == "SSH-2.0-X"
    assert row[1] is None


def test_client_kex_only_row(writer: EventWriter, db_connection: DbConn) -> None:
    """kex arriving alone leaves client_version NULL."""
    writer.write_event(_connect_event())
    writer.write_event(ClientKex(session_id="sess-001", hassh="cafe", timestamp=_TS))
    row = db_connection.execute(
        "SELECT client_version, hassh FROM ssh_clients WHERE session_id = %s",
        ("sess-001",),
    ).fetchone()
    assert row is not None
    assert row[0] is None
    assert row[1] == "cafe"
