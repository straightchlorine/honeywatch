"""Drip synthetic sessions into the dev database so the live feed actually moves.

`seed_dev.py` spreads its rows across a 7-day window, which is right for the
charts and useless for the Overview feed: that panel sorts by `recent` and
polls every 20s, so nothing new ever arrives and the map arcs never fire. This
inserts a handful of sessions stamped NOW, on an interval, until interrupted.

    just seed-live                    # 1-3 sessions every 15s, forever
    just seed-live --interval 5       # faster
    just seed-live --once             # a single tick

Append-only: it never wipes, and it reuses seed_dev's country pool so every
session geo-resolves and the arcs have real coordinates to fly between.
Rows are stamped sensor="seed" like the rest of the synthetic data.
"""

from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as DbSession

from scripts.seed_dev import (
    HONEYPOT_IP,
    SEED_SENSOR,
    build_ip_pool,
    bulk_insert,
    child_rows,
    geo_rows,
)
from src.config import Config
from src.models import AuthAttempt, Command, GeoLocation, Session


def tick_rows(rng: random.Random, ips: list[str], n: int) -> list[dict[str, Any]]:
    """`n` sessions that started in the last few seconds."""
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        started = now - timedelta(seconds=rng.uniform(0, 5))
        proto = "telnet" if rng.random() < 0.15 else "ssh"
        rows.append(
            {
                # Unique per tick: seed_dev's "seed-%07d" scheme collides the
                # moment this runs twice.
                "id": f"live-{int(started.timestamp() * 1000)}-{i}",
                "src_ip": rng.choice(ips),
                "src_port": rng.randint(1024, 65535),
                "dst_ip": HONEYPOT_IP,
                "dst_port": 23 if proto == "telnet" else 22,
                "protocol": proto,
                "started_at": started,
                "ended_at": started + timedelta(seconds=rng.uniform(1, 90)),
                "sensor": SEED_SENSOR,
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--interval", type=float, default=15.0, help="seconds between ticks")
    p.add_argument("--per-tick", type=int, default=3, help="max sessions per tick")
    p.add_argument(
        "--ip-pool", type=int, default=60, help="distinct source IPs to cycle"
    )
    p.add_argument("--once", action="store_true", help="insert one tick and exit")
    args = p.parse_args()

    rng = random.Random()
    ips = build_ip_pool(rng, args.ip_pool)
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

    # Geo first, once: without it the feed renders "Unknown" and the arcs have
    # no coordinates. ON CONFLICT so re-running never trips the ip primary key.
    with DbSession(engine) as db:
        rows = geo_rows(rng, ips)
        db.execute(
            pg_insert(GeoLocation).on_conflict_do_nothing(index_elements=["ip"]), rows
        )
        db.commit()
    print(
        f"geo ready for {len(ips)} IPs; "
        f"dripping every {args.interval}s (ctrl-c to stop)"
    )

    total = 0
    try:
        while True:
            n = rng.randint(1, max(1, args.per_tick))
            sessions = tick_rows(rng, ips, n)
            auth, cmds = child_rows(rng, sessions)
            with DbSession(engine) as db:
                bulk_insert(db, Session, sessions)
                if auth:
                    db.execute(insert(AuthAttempt), auth)
                if cmds:
                    db.execute(insert(Command), cmds)
                db.commit()
            total += n
            newest = sessions[-1]
            print(
                f"  +{n} session(s), {total} total "
                f"({newest['protocol']} from {newest['src_ip']})"
            )
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nstopped after {total} sessions")


if __name__ == "__main__":
    main()
