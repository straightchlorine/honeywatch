"""Unit tests for `src.geoip`.

Tests resilience to corrupt mmdbs and malformed arguments (production traffic
pre-validates via writer.py, so this is the only place raw input is checked).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import geoip2.errors
import pytest

from src import geoip


@pytest.fixture(autouse=True)
def _isolated_geoip_state() -> Generator[None]:
    """Reset module globals; lru_cache and readers leak state between tests."""
    geoip.close()
    geoip._warned.clear()
    yield
    geoip.close()
    geoip._warned.clear()


def test_lookup_returns_none_for_corrupt_mmdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    city_path = tmp_path / "GeoLite2-City.mmdb"
    asn_path = tmp_path / "GeoLite2-ASN.mmdb"
    city_path.write_bytes(b"not a real mmdb file")
    asn_path.write_bytes(b"not a real mmdb file either")
    monkeypatch.setattr(geoip, "_CITY_PATH", city_path)
    monkeypatch.setattr(geoip, "_ASN_PATH", asn_path)

    assert geoip.lookup("8.8.8.8") is None


def test_corrupt_mmdb_warns_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    city_path = tmp_path / "GeoLite2-City.mmdb"
    asn_path = tmp_path / "GeoLite2-ASN.mmdb"
    city_path.write_bytes(b"garbage")
    asn_path.write_bytes(b"garbage")
    monkeypatch.setattr(geoip, "_CITY_PATH", city_path)
    monkeypatch.setattr(geoip, "_ASN_PATH", asn_path)

    with caplog.at_level("WARNING", logger="src.geoip"):
        # Multiple IPs to trigger _open_readers each time (lru_cache would
        # otherwise return cached None without re-entering).
        geoip.lookup("8.8.8.8")
        geoip.lookup("1.1.1.1")

    corrupt_warnings = [r for r in caplog.records if "corrupt" in r.message.lower()]
    assert len(corrupt_warnings) == 1


def test_corrupt_mmdb_leaves_readers_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    city_path = tmp_path / "GeoLite2-City.mmdb"
    asn_path = tmp_path / "GeoLite2-ASN.mmdb"
    city_path.write_bytes(b"garbage")
    asn_path.write_bytes(b"garbage")
    monkeypatch.setattr(geoip, "_CITY_PATH", city_path)
    monkeypatch.setattr(geoip, "_ASN_PATH", asn_path)

    geoip.lookup("8.8.8.8")

    assert geoip._city_reader is None
    assert geoip._asn_reader is None


class _WorkingReader:
    """Stand-in for a `geoip2.database.Reader` backed by a healthy mmdb.

    No valid GeoLite2 mmdb is bundled with the repo (they're fetched via
    MAXMIND_* secrets that CI doesn't have - see test_writer.py's
    `test_geo_enrichment_populates_geo_locations`, which skips without
    them). Recording every call lets the malformed-argument tests below
    prove `lookup()`'s own input gate rejects bad input *before* ever
    reaching a working database, rather than merely observing a None
    result that a corrupt-database catch could equally have produced.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def city(self, ip: str) -> None:
        self.calls.append(ip)
        raise geoip2.errors.AddressNotFoundError("not found", ip_address=ip)

    def asn(self, ip: str) -> None:
        self.calls.append(ip)
        raise geoip2.errors.AddressNotFoundError("not found", ip_address=ip)


@pytest.fixture
def working_readers(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_WorkingReader, _WorkingReader]:
    """Install an already-open, non-corrupt reader pair.

    Setting the module-level readers directly (rather than pointing
    `_CITY_PATH`/`_ASN_PATH` at real files) makes `_open_readers` treat the
    database as already successfully opened - exactly the state it would be
    in after a real, valid mmdb load - without needing a real mmdb on disk.
    """
    city_reader = _WorkingReader()
    asn_reader = _WorkingReader()
    monkeypatch.setattr(geoip, "_city_reader", city_reader)
    monkeypatch.setattr(geoip, "_asn_reader", asn_reader)
    return city_reader, asn_reader


@pytest.mark.parametrize(
    "bad_input",
    [None, "", "not-an-ip-address", "1" * 10000],
    ids=["none", "empty-string", "garbage-text", "oversized-string"],
)
def test_lookup_never_raises_for_malformed_argument(
    bad_input: str | None,
    working_readers: tuple[_WorkingReader, _WorkingReader],
) -> None:
    """`lookup` must not raise on adversarial arguments against a working db.

    The module docstring promises `lookup` "never raises" as a general
    contract, not just resilience to a bad mmdb file. This is the only test
    that calls `lookup()` directly with a malformed argument instead of a
    pre-validated IP.
    """
    result = geoip.lookup(bad_input)

    assert result is None

    city_reader, asn_reader = working_readers
    # The working db is never touched: bad input is rejected by lookup()'s
    # own `not ip or not _is_public(ip)` gate before _open_readers runs.
    assert city_reader.calls == []
    assert asn_reader.calls == []
