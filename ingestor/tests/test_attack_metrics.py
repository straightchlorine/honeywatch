"""Attack counters (new rows only) and the METRICS_TEXTFILE writer."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from prometheus_client import REGISTRY
from prometheus_client.parser import text_string_to_metric_families

from src import main as main_module
from src import metrics
from src import writer as writer_module
from src.events import (
    CommandInput,
    DirectTcpipRequest,
    FileDownload,
    LoginFailed,
    LoginSuccess,
    SessionConnect,
)
from src.geoip import GeoData
from src.writer import EventWriter, _country_label

# db_connection truncates after each test; without it these sessions would
# persist and dedupe on the next run.
pytestmark = pytest.mark.usefixtures("db_connection")

_TS = datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc)


def _attack(kind: str) -> float:
    return (
        REGISTRY.get_sample_value("ingestor_attack_events_total", {"type": kind}) or 0.0
    )


def _country(code: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "ingestor_sessions_by_country_total", {"country": code}
        )
        or 0.0
    )


def _connect(sid: str = "sess-am-1", ip: str = "198.51.100.7") -> SessionConnect:
    return SessionConnect(
        session_id=sid,
        src_ip=ip,
        src_port=1111,
        dst_ip="10.0.0.1",
        dst_port=2222,
        protocol="ssh",
        timestamp=_TS,
        sensor="honeypot-01",
    )


def _geo(code: str | None) -> GeoData:
    return GeoData(
        country_code=code,
        country="X",
        city=None,
        latitude=0.0,
        longitude=0.0,
        asn=1,
        as_org="Org",
    )


# --- country label ---


@pytest.mark.parametrize("code", ["US", "PL", "ZZ"])
def test_country_label_accepts_alpha2(code: str) -> None:
    assert _country_label(code) == code


@pytest.mark.parametrize(
    "code", [None, "", "U", "USA", "us", "U1", "UŠ", "US\n", "<script>"]
)
def test_country_label_rejects_everything_else(code: str | None) -> None:
    assert _country_label(code) == "unknown"


# --- counters (need Postgres) ---


def test_session_counts_once_and_not_on_replay(writer: EventWriter) -> None:
    s0, c0 = _attack("session"), _country("DE")
    with patch.object(writer_module, "geoip_lookup", return_value=_geo("DE")):
        writer.write_event(_connect())
        writer.write_event(_connect())
    assert _attack("session") == s0 + 1
    assert _country("DE") == c0 + 1


def test_country_counted_when_geo_lookup_is_ttl_skipped(writer: EventWriter) -> None:
    """Second session from a recently-upserted IP still counts its country."""
    c0 = _country("FR")
    with patch.object(writer_module, "geoip_lookup", return_value=_geo("FR")) as m:
        writer.write_event(_connect("sess-am-a", "198.51.100.8"))
        writer.write_event(_connect("sess-am-b", "198.51.100.8"))
    assert m.call_count == 1
    assert _country("FR") == c0 + 2


def test_country_counted_when_ip_was_cached_as_tcpip_dest(writer: EventWriter) -> None:
    """An IP geo-enriched as a direct-tcpip destination keeps its country when
    it later connects as a session source within the TTL."""
    c0 = _country("NL")
    with patch.object(writer_module, "geoip_lookup", return_value=_geo("NL")):
        writer.write_event(_connect("sess-am-t", "198.51.100.20"))
        writer.write_event(
            DirectTcpipRequest(
                session_id="sess-am-t",
                dst_ip="198.51.100.12",
                dst_port=25,
                src_ip="10.0.0.1",
                src_port=40000,
                timestamp=_TS,
            )
        )
        writer.write_event(_connect("sess-am-u", "198.51.100.12"))
    assert _country("NL") == c0 + 2


def test_country_unknown_when_lookup_returns_nothing(writer: EventWriter) -> None:
    u0 = _country("unknown")
    with patch.object(writer_module, "geoip_lookup", return_value=None):
        writer.write_event(_connect("sess-am-n", "198.51.100.9"))
    assert _country("unknown") == u0 + 1


def test_malformed_country_code_becomes_unknown(writer: EventWriter) -> None:
    u0 = _country("unknown")
    with patch.object(writer_module, "geoip_lookup", return_value=_geo("usa")):
        writer.write_event(_connect("sess-am-m", "198.51.100.10"))
    assert _country("unknown") == u0 + 1
    assert _country("usa") == 0.0


def test_loopback_connect_is_not_counted(db_url: str) -> None:
    s0, u0 = _attack("session"), _country("unknown")
    with EventWriter(db_url, drop_loopback=True) as w:
        w.write_event(_connect("sess-am-lo", "127.0.0.1"))
    assert _attack("session") == s0
    assert _country("unknown") == u0


def test_child_events_count_once_and_not_on_replay(writer: EventWriter) -> None:
    before = {
        k: _attack(k) for k in ("login_success", "login_failed", "command", "download")
    }
    with patch.object(writer_module, "geoip_lookup", return_value=None):
        writer.write_event(_connect("sess-am-c", "198.51.100.11"))
    events = [
        LoginFailed(session_id="sess-am-c", username="a", password="b", timestamp=_TS),
        LoginSuccess(
            session_id="sess-am-c",
            username="a",
            password="c",
            timestamp=_TS.replace(second=9),
        ),
        CommandInput(session_id="sess-am-c", input="ls", timestamp=_TS),
        FileDownload(
            session_id="sess-am-c",
            url="http://x/y",
            outfile="/tmp/y",
            sha256="0" * 64,
            timestamp=_TS,
        ),
    ]
    for e in events:
        writer.write_event(e)
        writer.write_event(e)  # replay
    assert _attack("login_failed") == before["login_failed"] + 1
    assert _attack("login_success") == before["login_success"] + 1
    assert _attack("command") == before["command"] + 1
    assert _attack("download") == before["download"] + 1


def test_orphan_child_event_is_not_counted(writer: EventWriter) -> None:
    c0 = _attack("command")
    writer.write_event(CommandInput(session_id="no-such", input="ls", timestamp=_TS))
    assert _attack("command") == c0


def test_geo_upsert_failure_keeps_country_and_is_not_cached(
    writer: EventWriter,
) -> None:
    f0 = REGISTRY.get_sample_value("ingestor_geo_upsert_failures_total") or 0.0
    c0 = _country("SE")
    with (
        patch.object(writer_module, "geoip_lookup", return_value=_geo("SE")) as m,
        patch.object(writer_module, "_UPSERT_GEO", "SELECT * FROM no_such_table"),
    ):
        writer.write_event(_connect("sess-am-g1", "198.51.100.13"))
        writer.write_event(_connect("sess-am-g2", "198.51.100.13"))
    assert REGISTRY.get_sample_value("ingestor_geo_upsert_failures_total") == f0 + 2
    assert m.call_count == 2  # a failed upsert must not start the TTL
    assert _country("SE") == c0 + 2


def test_dropped_session_is_not_counted(writer: EventWriter) -> None:
    s0, u0 = _attack("session"), _country("unknown")
    bad = _connect("sess-am-d", "198.51.100.14").model_copy(update={"dst_port": 2**31})
    with patch.object(writer_module, "geoip_lookup", return_value=None) as m:
        writer.write_event(bad)  # INT4 overflow -> DataError -> dropped
    assert m.call_count == 0
    assert _attack("session") == s0
    assert _country("unknown") == u0


# --- textfile writer (no DB needed, but session fixtures require it anyway) ---


def test_textfile_has_only_ingestor_metrics(tmp_path: Path) -> None:
    out = tmp_path / "ingestor.prom"
    # Labelled counters only render once a child exists.
    metrics.attack_events_total.labels(type="session").inc(0)
    main_module._write_textfile(out)
    text = out.read_text()
    names = {f.name for f in text_string_to_metric_families(text)}
    assert "ingestor_attack_events" in names
    assert "ingestor_queue_depth" in names
    assert "ingestor_fuse_blown" in names  # unlabelled counter, always rendered
    assert "ingestor_attack_events_total" in text
    assert "_created" not in text
    assert not [n for n in names if not n.startswith("ingestor_")]
    assert [p.name for p in tmp_path.iterdir()] == ["ingestor.prom"]


def test_textfile_loop_survives_unwritable_path_and_warns_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "nope" / "ingestor.prom"
    stop = threading.Event()
    calls = 0
    real = main_module._write_textfile

    def spy(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            missing.parent.mkdir()  # recovery
        if calls == 4:
            stop.set()
        real(path)

    with caplog.at_level(logging.WARNING, logger="src.main"):
        with patch.object(main_module, "_write_textfile", spy):
            main_module._textfile_loop(missing, stop, interval=0.01)

    warnings = [r.getMessage() for r in caplog.records]
    assert sum("failed to write" in w for w in warnings) == 1
    assert sum("writable again" in w for w in warnings) == 1
    assert missing.exists()


def test_config_metrics_textfile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import Config

    for k, v in {
        "POSTGRES_USER": "u",
        "POSTGRES_PASSWORD": "p",
        "POSTGRES_DB": "d",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("METRICS_TEXTFILE", raising=False)
    assert Config.from_env().metrics_textfile is None
    monkeypatch.setenv("METRICS_TEXTFILE", "/metrics/ingestor.prom")
    assert Config.from_env().metrics_textfile == Path("/metrics/ingestor.prom")
