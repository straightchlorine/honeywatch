#!/usr/bin/env python3
"""Regenerate `ingestor/tests/fixtures/cowrie_sample.jsonl` from real cowrie output.

Reads a cowrie JSONL stream (file path arg or stdin), keeps one of each
`eventid` the writer dispatches on plus the always-emitted `client.*`
events, rewrites every `session` field to a single canonical id so the
contract test reads a tidy single-session record, and prints the result.

Usage::

    docker exec honeywatch-cowrie cat /logs/cowrie.json \\
        | scripts/regen_cowrie_fixture.py \\
        > ingestor/tests/fixtures/cowrie_sample.jsonl
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

CANONICAL_SESSION_ID = "contract-sess-01"

# Order matters: contract test assertions assume connect comes first so
# the child-row FKs (auth/cmd/download/fingerprint/direct-tcpip) land cleanly,
# and session.closed comes last so `ended_at` is populated.
WANTED_EVENTIDS = (
    "cowrie.session.connect",
    "cowrie.client.version",
    "cowrie.client.kex",
    "cowrie.client.size",
    "cowrie.login.failed",
    "cowrie.login.success",
    "cowrie.client.fingerprint",
    "cowrie.command.input",
    "cowrie.session.file_download",
    "cowrie.direct-tcpip.request",
    "cowrie.session.closed",
)


def _read(source: Iterable[str]) -> dict[str, dict[str, object]]:
    picked: dict[str, dict[str, object]] = {}
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        eventid = obj.get("eventid")
        if not isinstance(eventid, str):
            continue
        if eventid not in WANTED_EVENTIDS or eventid in picked:
            continue
        obj["session"] = CANONICAL_SESSION_ID
        picked[eventid] = obj
    return picked


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: regen_cowrie_fixture.py [path]", file=sys.stderr)
        return 2

    source: Iterable[str]
    if len(argv) == 2:
        source = Path(argv[1]).read_text(encoding="utf-8").splitlines()
    else:
        source = sys.stdin

    picked = _read(source)
    missing = [eid for eid in WANTED_EVENTIDS if eid not in picked]
    if missing:
        print(
            f"missing eventids in capture: {missing}; regen aborted",
            file=sys.stderr,
        )
        return 1

    for eid in WANTED_EVENTIDS:
        print(json.dumps(picked[eid], separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
