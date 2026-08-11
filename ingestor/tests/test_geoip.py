"""Unit tests for `src.geoip`, focused on the corrupt-mmdb never-raise contract."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from src import geoip


@pytest.fixture(autouse=True)
def _isolated_geoip_state() -> Generator[None]:
    """Reset module globals so tests don't leak cached readers/warnings.

    `_lookup_cached` is `lru_cache`d and the readers live in module globals,
    so a prior test's state would otherwise poison this one.
    """
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
        # Two different IPs so the lru_cache doesn't just return the same
        # cached None without re-entering _open_readers.
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
