"""GeoIP enrichment using local MaxMind GeoLite2 databases.

Two .mmdb files are loaded lazily on first lookup:
- GeoLite2-City.mmdb: country, city, lat/lng
- GeoLite2-ASN.mmdb:  ASN + organization

Files live under GEOIP_DATA_DIR (default /data/geoip) and are baked into
the ingestor image at build time. If the files are absent, every lookup
returns None and the ingestor keeps running unenriched. The absence is
logged once at warning level, not per-event.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import geoip2.database
import geoip2.errors

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("GEOIP_DATA_DIR", "/data/geoip"))
_CITY_PATH = _DATA_DIR / "GeoLite2-City.mmdb"
_ASN_PATH = _DATA_DIR / "GeoLite2-ASN.mmdb"


@dataclass(slots=True, frozen=True)
class GeoData:
    country_code: str | None
    country: str | None
    city: str | None
    latitude: float | None
    longitude: float | None
    asn: int | None
    as_org: str | None


_lock = Lock()
_city_reader: geoip2.database.Reader | None = None
_asn_reader: geoip2.database.Reader | None = None
# Set of warning keys already emitted, so each "databases missing"
# warning fires once per process instead of once per event.
_warned: set[str] = set()


_ReaderPair = tuple["geoip2.database.Reader | None", "geoip2.database.Reader | None"]


def _open_readers() -> _ReaderPair:
    # Both readers are opened together below; require both to be set
    # before so a partial init (e.g. ASN constructor raises after City
    # succeeded) mismatched (Reader, None) pair forever.
    global _city_reader, _asn_reader
    with _lock:
        if _city_reader is not None and _asn_reader is not None:
            return _city_reader, _asn_reader
        if not _CITY_PATH.exists() or not _ASN_PATH.exists():
            if "missing" not in _warned:
                logger.warning(
                    "GeoIP databases missing at %s; geo enrichment disabled "
                    "(City: %s, ASN: %s)",
                    _DATA_DIR,
                    _CITY_PATH.exists(),
                    _ASN_PATH.exists(),
                )
                _warned.add("missing")
            return None, None
        _city_reader = geoip2.database.Reader(str(_CITY_PATH))
        _asn_reader = geoip2.database.Reader(str(_ASN_PATH))
        logger.info("GeoIP readers opened from %s", _DATA_DIR)
        return _city_reader, _asn_reader


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def lookup(ip: str | None) -> GeoData | None:
    """Resolve City + ASN for a public IP. Returns None for private/missing.

    Safe to call with None or with private/reserved IPs - they short-circuit
    before touching the readers.
    """
    if not ip or not _is_public(ip):
        return None
    city_reader, asn_reader = _open_readers()
    if city_reader is None or asn_reader is None:
        return None

    country_code = country = city = None
    latitude = longitude = None
    asn = as_org = None

    try:
        c = city_reader.city(ip)
        country_code = c.country.iso_code
        country = c.country.name
        city = c.city.name
        latitude = c.location.latitude
        longitude = c.location.longitude
    except geoip2.errors.AddressNotFoundError:
        pass  # city DB doesn't cover this IP - still try ASN

    try:
        a = asn_reader.asn(ip)
        asn = a.autonomous_system_number
        as_org = a.autonomous_system_organization
    except geoip2.errors.AddressNotFoundError:
        # ASN DB doesn't cover this IP - keep any partial city-only
        # result. Treated as a full miss only if city was also empty
        pass

    # If neither DB had anything, treat as miss.
    if country_code is None and asn is None:
        return None

    return GeoData(
        country_code=country_code,
        country=country,
        city=city,
        latitude=latitude,
        longitude=longitude,
        asn=asn,
        as_org=as_org,
    )


def close() -> None:
    """Close readers; called once at process shutdown if needed."""
    global _city_reader, _asn_reader
    with _lock:
        if _city_reader is not None:
            _city_reader.close()
            _city_reader = None
        if _asn_reader is not None:
            _asn_reader.close()
            _asn_reader = None
