"""One-off maintenance CLI: force a fresh GeoIP reclassification of known IPs.

`writer.EventWriter` only refreshes an IP's `geo_locations` row when that
exact IP reconnects to the honeypot (and its in-process TTL throttle has
expired). That means a wrong or missing classification - e.g. after the
bundled MaxMind mmdb is updated at a later deploy, or enrichment was
transiently broken when a session first landed - stays wrong until the
attacker happens to come back. This script re-runs `geoip.lookup` against
every IP we've ever seen (or a single `--ip`) and upserts the result,
independent of the ingestor's own connect-triggered enrichment path.

Not a public API endpoint - run locally/CI-adjacent against the database,
the same way `just seed` or `just db upgrade` are run. Safe to run
repeatedly and safe to run alongside the live ingestor process: it only
ever writes to `geo_locations`, and each invocation is a fresh process with
an empty `lru_cache`, so no shared state with the running ingestor.

Usage:
    python -m src.reclassify_geoip              # every IP ever seen
    python -m src.reclassify_geoip --ip 1.2.3.4  # just one IP
"""

from __future__ import annotations

import argparse
import logging

import psycopg

from src.config import Config
from src.geoip import lookup as geoip_lookup
from src.sanitize import truncate
from src.writer import (
    _LEN_AS_ORG,
    _LEN_CITY,
    _LEN_COUNTRY,
    _LEN_COUNTRY_CODE,
    _UPSERT_GEO,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_PROGRESS_EVERY = 500

# Union covers all known IPs (existing geo_locations + sessions.src_ip +
# direct_tcpip_requests.dst_ip) to catch stale or missing enrichment.
# pg_input_is_valid handles IPv6 and validates formats more robustly than regex.
# Kept as INET type (not ::text) to avoid psycopg rendering netmask suffix.
_SELECT_ALL_KNOWN_IPS = """
    SELECT ip FROM geo_locations
    UNION
    SELECT src_ip FROM sessions WHERE src_ip IS NOT NULL
    UNION
    SELECT dst_ip::inet FROM direct_tcpip_requests
    WHERE pg_input_is_valid(dst_ip, 'inet')
"""

_SELECT_EXISTING_GEO = """
    SELECT country_code, country, city, latitude, longitude, asn, as_org
    FROM geo_locations WHERE ip = %(ip)s
"""


def _target_ips(conn: psycopg.Connection, ip: str | None) -> list[str]:
    """Return the IPs to reclassify: just `ip` if given, else every known IP."""
    if ip is not None:
        return [ip]
    rows = conn.execute(_SELECT_ALL_KNOWN_IPS).fetchall()
    return [str(row[0]) for row in rows]


def _reclassify_one(conn: psycopg.Connection, ip: str) -> bool | None:
    """Look up `ip` and upsert it into geo_locations.

    Returns:
        None if the fresh lookup was unenrichable (no upsert performed).
        True if the upserted values differ from what was already stored
        (or no row existed yet); False if they're identical to before.
    """
    geo = geoip_lookup(ip)
    if geo is None:
        return None

    before = conn.execute(_SELECT_EXISTING_GEO, {"ip": ip}).fetchone()
    params = {
        "ip": ip,
        "country_code": truncate(geo.country_code, _LEN_COUNTRY_CODE),
        "country": truncate(geo.country, _LEN_COUNTRY),
        "city": truncate(geo.city, _LEN_CITY),
        "latitude": geo.latitude,
        "longitude": geo.longitude,
        "asn": geo.asn,
        "as_org": truncate(geo.as_org, _LEN_AS_ORG),
    }
    after = (
        params["country_code"],
        params["country"],
        params["city"],
        params["latitude"],
        params["longitude"],
        params["asn"],
        params["as_org"],
    )
    with conn.transaction():
        conn.execute(_UPSERT_GEO, params)
    return before is None or tuple(before) != after


def reclassify(conninfo: str, ip: str | None) -> None:
    """Reclassify `ip`, or every known IP if `ip` is None, at the DB at `conninfo`."""
    with psycopg.connect(conninfo) as conn:
        ips = _target_ips(conn, ip)
        total = len(ips)
        logger.info("reclassifying %d IP(s)", total)

        looked_up = changed = unenrichable = 0
        # geoip.lookup is a local mmdb read, not a network API; no rate
        # limiting needed.
        for i, target in enumerate(ips, start=1):
            looked_up += 1
            result = _reclassify_one(conn, target)
            if result is None:
                unenrichable += 1
            elif result:
                changed += 1
            if i % _PROGRESS_EVERY == 0:
                logger.info("progress: %d/%d IPs processed", i, total)

        unchanged = looked_up - changed - unenrichable
        logger.info(
            "done: looked_up=%d changed=%d unchanged=%d unenrichable=%d",
            looked_up,
            changed,
            unchanged,
            unenrichable,
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Force a fresh GeoIP reclassification of known IPs."
    )
    parser.add_argument(
        "--ip",
        default=None,
        help="Reclassify only this IP (default: every IP ever seen).",
    )
    args = parser.parse_args(argv)

    config = Config.from_env()
    reclassify(config.conninfo, args.ip)


if __name__ == "__main__":
    main()
