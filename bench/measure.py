#!/usr/bin/env python3
"""Measure the folded /sessions calls and append each measurement to a results CSV.

--repo names the tree under test, a git worktree from worktrees.sh. It is never
the checkout that hosts this script. `src` is imported from that tree, so run from
its api/ directory with the exports from `bench.sh env`; `just bench measure` does
both:

    just bench measure ../honeywatch-wt/0.8.5 --variant baseline --scenario layout

Scenarios:
  route   every GET route of the API through the Flask test client, in process
          (routes.py lists the requests): wall time, the request's own CPU, the
          database's CPU, payload bytes and HTTP status. Works on any release.
  layout  N builds of the layout pass through the path prod uses (serial plan, one
          slot). Build 0 is a warm-up; summarize.py drops it.
  page    one layout build, then timed get_sessions_folded() calls on a warm cache:
          page1, deep (page 300) and largest_run (the page holding the biggest run).
          The build's SET LOCAL settings are rolled back first, so the pages run the
          default plan, like a prod cache hit.

Every row carries a fingerprint of what the call returned (layout: total and run
boundaries; page: ids and run counts). fp_match_baseline compares it with the first
baseline row of the same scenario, sort and label. A different fingerprint means the
behaviour changed, not only the speed.

Numbers go into the CSV as they are measured and summarize.py renders the tables
from it. Do not copy numbers by hand.

The layout and page scenarios need v0.8.3 or later, where src.services.sessions is
a package. The route scenario also runs on older releases.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from typing import IO

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import routes
from src.config import Config

try:
    from src.services.sessions import cache, filters, layout, pages
except ImportError as exc:
    SESSIONS_MISSING = str(exc)
else:
    SESSIONS_MISSING = ""

HERE = pathlib.Path(__file__).resolve().parent
HOST_TREE = HERE.parent  # the checkout that hosts this script
DEFAULT_CSV = HERE / "results" / "results.csv"
CONTAINER = os.environ.get("BENCH_NAME", "hw-bench-pg")
PER_PAGE = 25
DEEP_PAGE = 300
SORTS = ["recent", "country", "active", "interest", "duration"]
FIELDS = (
    "ts run_id variant git_sha tree_hash alembic sessions caps "
    "scenario sort label build_idx wall_ms app_cpu_ms cpu_ms throttled_ms read_mb "
    "fingerprint fp_match_baseline rows bytes status note"
).split()

# What a timed call returns: what to fingerprint, and extra CSV columns.
Call = Callable[[], tuple[object, dict[str, object]]]


def sh(*cmd: str, cwd: pathlib.Path | None = None) -> str:
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return done.stdout.strip()


def psql(*args: str, stdin: IO[str] | None = None) -> None:
    cmd = ["docker", "exec", "-i", CONTAINER, "psql", "-q", "-U", "honeywatch"]
    subprocess.run(
        [*cmd, "-d", "honeywatch", "-v", "ON_ERROR_STOP=1", *args],
        stdin=stdin,
        check=True,
    )


class Cgroup:
    """cpu and io counters of the bench container (cgroup v2); empty if unreadable."""

    def __init__(self) -> None:
        cid = sh("docker", "inspect", "-f", "{{.Id}}", CONTAINER)
        self.dir = pathlib.Path(f"/sys/fs/cgroup/system.slice/docker-{cid}.scope")
        self.ok = bool(cid) and (self.dir / "cpu.stat").exists()
        if not self.ok:
            print(
                "warning: cgroup stats unreadable, so cpu_ms, throttled_ms and "
                "read_mb will be empty. Wall time alone is not comparable under a "
                "CPU quota.",
                file=sys.stderr,
            )

    def read(self) -> tuple[int, int, int] | None:
        if not self.ok:
            return None
        cpu = dict(
            ln.split() for ln in (self.dir / "cpu.stat").read_text().splitlines()
        )
        rbytes = sum(
            int(tok.split("=")[1])
            for ln in (self.dir / "io.stat").read_text().splitlines()
            for tok in ln.split()
            if tok.startswith("rbytes=")
        )
        return int(cpu["usage_usec"]), int(cpu["throttled_usec"]), rbytes


def caps() -> str:
    fmt = (
        "mem={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}} "
        "shm={{.HostConfig.ShmSize}} cpuset={{.HostConfig.CpusetCpus}}"
    )
    return sh("docker", "inspect", CONTAINER, "--format", fmt)


def fingerprint(obj: object) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha1(blob).hexdigest()[:12]


def data_shape(db: Session) -> dict[str, object]:
    """Identity of the dataset under test: two dumps are two different experiments.

    The layout pass is one ordered pass over the table, so its cost follows the row
    count and the heap state. A restore re-packs every table without dead tuples and
    resets the visibility map; prod carries both. Recorded once per run, so a later
    reader can tell whether two numbers saw the same data.
    """
    row = db.execute(
        text(
            "select count(*) as sessions, count(ended_at) as ended,"
            " max(started_at) as newest,"
            " pg_database_size(current_database()) as db_bytes from sessions"
        )
    ).one()
    correlation = db.execute(
        text(
            "select correlation from pg_stats where schemaname = 'public'"
            " and tablename = 'sessions' and attname = 'started_at'"
        )
    ).scalar()
    return {
        "sessions": row.sessions,
        "ended": row.ended,
        "newest": str(row.newest),
        "db_bytes": row.db_bytes,
        "started_at_correlation": None
        if correlation is None
        else round(correlation, 4),
    }


def read(path: str) -> str:
    try:
        return pathlib.Path(path).read_text().strip()
    except OSError:
        return ""


def os_fingerprint() -> dict[str, object]:
    """The layers below the container that move these numbers.

    Postgres and the API run in pinned images, so their userspace is the same on
    every host. A run is only comparable with one from the same kernel, cgroup
    version, THP mode, filesystem and Docker driver.
    """
    try:
        osr = platform.freedesktop_os_release()
    except OSError:
        osr = {}
    thp = read("/sys/kernel/mm/transparent_hugepage/enabled")
    cgroup_v2 = pathlib.Path("/sys/fs/cgroup/cgroup.controllers").exists()
    return {
        "distro": osr.get("PRETTY_NAME", "unknown"),
        "distro_id": osr.get("ID", "unknown"),
        "cgroup_version": "v2" if cgroup_v2 else "v1",
        "thp": thp[thp.find("[") + 1 : thp.find("]")] if "[" in thp else "unknown",
        "docker_driver": sh("docker", "info", "--format", "{{.Driver}}") or "unknown",
        "docker_root_fs": sh("stat", "-f", "-c", "%T", "/var/lib/docker") or "unknown",
    }


class HostProbe:
    """Which machine is measuring. Numbers from two hosts never share a table."""

    def __init__(self) -> None:
        cpuinfo = pathlib.Path("/proc/cpuinfo").read_text().splitlines()
        cpu = next(
            (
                ln.split(":", 1)[1].strip()
                for ln in cpuinfo
                if ln.startswith("model name")
            ),
            "unknown",
        )
        mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        self.info = {
            "host": platform.node(),
            "cpu_model": cpu,
            "logical_cpus": os.cpu_count(),
            "mem_total_mb": mem // 2**20,
            "kernel": platform.release(),
            **os_fingerprint(),
        }
        self.steal0 = self.steal()

    @staticmethod
    def steal() -> int:
        """Cumulative steal ticks of the aggregate cpu line; 0 on bare metal."""
        fields = pathlib.Path("/proc/stat").read_text().splitlines()[0].split()
        return int(fields[8]) if len(fields) > 8 and fields[8].isdigit() else 0

    def finish(self) -> dict[str, object]:
        ticks = self.steal() - self.steal0
        return {**self.info, "steal_ms": round(ticks * 1000 / os.sysconf("SC_CLK_TCK"))}


class Recorder:
    def __init__(self, args: argparse.Namespace, db: Session) -> None:
        self.args = args
        self.run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        self.host = HostProbe()
        self.cg = Cgroup()
        diff = sh("git", "diff", "HEAD", "--", "api", "ingestor", cwd=args.repo)
        self.static = {
            "variant": args.variant,
            "git_sha": sh("git", "rev-parse", "--short", "HEAD", cwd=args.repo),
            "tree_hash": hashlib.sha1(diff.encode()).hexdigest()[:8]
            if diff
            else "clean",
            "alembic": db.execute(
                text("select version_num from alembic_version")
            ).scalar(),
            "sessions": db.execute(text("select count(*) from sessions")).scalar(),
            "caps": caps(),
        }
        self.baseline = self.load_baseline()
        self.data = data_shape(db)
        print(
            f"data: {self.data['sessions']} sessions, {self.data['ended']} ended, "
            f"newest {self.data['newest']}, db {self.data['db_bytes']} bytes, "
            f"corr(started_at)={self.data['started_at_correlation']}"
        )
        print(f"host: {self.host.info['cpu_model']}")
        new = not args.csv.exists() or args.csv.stat().st_size == 0
        if not new and args.csv.read_text().split("\n", 1)[0].split(",") != FIELDS:
            sys.exit(f"{args.csv} has an older column set; start a new file with --csv")
        self.f = args.csv.open("a", newline="")
        self.w = csv.DictWriter(self.f, FIELDS)
        if new:
            self.w.writeheader()

    def load_baseline(self) -> dict[tuple[str, str, str], str]:
        base: dict[tuple[str, str, str], str] = {}
        if self.args.csv.exists():
            with self.args.csv.open(newline="") as fh:
                for r in csv.DictReader(fh):
                    if r["variant"] == "baseline":
                        base.setdefault(
                            (r["scenario"], r["sort"], r["label"]), r["fingerprint"]
                        )
        return base

    def measure(
        self, scenario: str, sort: str, label: str, idx: int, call: Call
    ) -> None:
        before = self.cg.read()
        cpu0, t = time.process_time(), time.perf_counter()
        fp_source, extra = call()
        wall = (time.perf_counter() - t) * 1000
        app_cpu = (time.process_time() - cpu0) * 1000
        after = self.cg.read()
        fp = fingerprint(fp_source)
        key = (scenario, sort, label)
        if self.args.variant == "baseline":
            self.baseline.setdefault(key, fp)
        match = str(self.baseline[key] == fp) if key in self.baseline else ""
        cg = ["", "", ""]
        if before and after:
            usec = [(a - b) for a, b in zip(after, before, strict=True)]
            cg = [round(usec[0] / 1000), round(usec[1] / 1000), round(usec[2] / 1e6, 1)]
        row = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "run_id": self.run_id,
            **self.static,
            "scenario": scenario,
            "sort": sort,
            "label": label,
            "build_idx": idx,
            "wall_ms": round(wall),
            "app_cpu_ms": round(app_cpu),
            "cpu_ms": cg[0],
            "throttled_ms": cg[1],
            "read_mb": cg[2],
            "fingerprint": fp,
            "fp_match_baseline": match,
            "rows": "",
            "bytes": "",
            "status": "",
            **extra,
            "note": self.args.note,
        }
        self.w.writerow(row)
        self.f.flush()
        print(
            f"{scenario:6} {sort:8} {label[:44]:44} #{idx} wall={row['wall_ms']:>5}ms "
            f"app={row['app_cpu_ms']:>5}ms db={cg[0]!s:>5}ms "
            f"bytes={extra.get('bytes', '')!s:>7} fp={fp} match={match}"
        )

    def finish(self) -> None:
        """Write the run's provenance next to the CSV: host, data, caps, tree."""
        self.f.close()
        out = self.args.csv.parent / "runs"
        out.mkdir(parents=True, exist_ok=True)
        finished = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        meta = {
            "run_id": self.run_id,
            "started": self.started,
            "finished": finished,
            "csv": str(self.args.csv),
            "repo": str(self.args.repo),
            "note": self.args.note,
            **self.static,
            "data": self.data,
            **self.host.finish(),
        }
        path = out / f"{self.run_id}-{self.args.variant}.json"
        path.write_text(json.dumps(meta, indent=2, sort_keys=True, default=str) + "\n")
        print(f"run metadata: {path}")


def measure_layout(
    rec: Recorder, factory: sessionmaker[Session], sort: str, builds: int
) -> None:
    order = filters.SORT_DEFAULT_DIRECTION[sort]

    def build() -> tuple[object, dict[str, object]]:
        with factory() as db:
            lay = cache._build_in_slot(
                db, lambda d: layout.build_layout(d, [], sort, order), 60
            )
        assert lay is not None, "layout build failed"
        return (lay.total, lay.rows_before, lay.hidden), {"rows": lay.rows}

    for i in range(builds):
        rec.measure("layout", sort, "build", i, build)


def measure_pages(
    rec: Recorder, factory: sessionmaker[Session], sort: str, repeat: int
) -> None:
    cache.clear_layout_cache()
    with factory() as db:
        # Builds and caches the layout; not measured.
        pages.get_sessions_folded(db, 1, PER_PAGE, sort=sort)
        # The build set work_mem and a serial plan with SET LOCAL. End that
        # transaction so the page calls run the default plan, like a prod cache hit.
        db.rollback()
        lay = next(iter(cache._layouts.values()))
        targets = {"page1": 1, "deep": DEEP_PAGE}
        if lay.hidden:
            sizes = [
                b - a + 1 for a, b in zip([0, *lay.hidden], lay.hidden, strict=False)
            ]
            biggest = sizes.index(max(sizes))
            targets["largest_run"] = lay.rows_before[biggest] // PER_PAGE + 1
        for label, page in targets.items():

            def call(page: int = page) -> tuple[object, dict[str, object]]:
                r = pages.get_sessions_folded(db, page, PER_PAGE, sort=sort)
                shown = [
                    (s["id"], (s["run"] or {}).get("count")) for s in r["sessions"]
                ]
                return shown, {"rows": len(r["sessions"])}

            for i in range(repeat):
                rec.measure("page", sort, label, i, call)


def strip_as_of(doc: object) -> object:
    """Drop the snapshot time: it differs per build and says nothing about behaviour."""
    if isinstance(doc, dict):
        return {k: strip_as_of(v) for k, v in doc.items() if k != "as_of"}
    if isinstance(doc, list):
        return [strip_as_of(v) for v in doc]
    return doc


def measure_routes(
    rec: Recorder, factory: sessionmaker[Session], repeat: int, only: list[str]
) -> None:
    from src.app import create_app

    app = create_app()
    client = app.test_client()
    with factory() as db:
        paths = routes.cases(routes.lookups(db))
    if (run := routes.run_members(client)) is not None:
        paths.append(run)
    for rule in routes.uncovered(app):
        print(f"warning: route not covered by bench/routes.py: {rule}", file=sys.stderr)
    for path in paths:
        if only and not any(o in path for o in only):
            continue
        client.get(path)  # warm-up: fills the layout cache and the page cache

        def call(path: str = path) -> tuple[object, dict[str, object]]:
            r = client.get(path)
            body = r.get_data()
            doc = strip_as_of(r.get_json(silent=True)) or body.decode(errors="replace")
            if path.startswith(routes.TIME_RELATIVE):
                doc = routes.shape(doc)
            return doc, {"bytes": len(body), "status": r.status_code}

        for i in range(repeat):
            rec.measure("route", "GET", routes.label(path), i, call)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add = p.add_argument
    path = pathlib.Path
    add("--repo", required=True, type=path, help="tree under test (a worktree)")
    add("--csv", type=path, default=DEFAULT_CSV, help="results CSV to append to")
    add("--variant", required=True, help="what is tested; the first run is 'baseline'")
    add("--scenario", choices=["route", "layout", "page"], required=True)
    add("--sort", nargs="+", default=["recent"], choices=SORTS)
    add(
        "--only",
        nargs="+",
        default=[],
        help="route: only paths containing one of these",
    )
    add(
        "--builds",
        type=int,
        default=6,
        help="layout: builds per sort, first is warm-up",
    )
    add("--repeat", type=int, default=5, help="route, page: calls per request")
    add(
        "--cold",
        action="store_true",
        help="restart Postgres first (shared_buffers only)",
    )
    add("--sql-before", help="SQL file applied first, then ANALYZE (e.g. CREATE INDEX)")
    add("--sql-after", help="SQL file applied last (e.g. DROP INDEX), back to baseline")
    add("--note", default="", help="free text stored on every row")
    args = p.parse_args()

    args.repo = args.repo.resolve()
    args.csv = args.csv.resolve()
    if not (args.repo / "api" / "src").is_dir():
        sys.exit(f"--repo {args.repo} is not a honeywatch checkout (no api/src)")
    dirty = sh("git", "status", "--porcelain", "--", "api", "ingestor", cwd=args.repo)
    if args.repo == HOST_TREE and dirty:
        sys.exit(
            "refusing to measure uncommitted api/ingestor changes in the checkout "
            "that hosts the bench.\nPut the change in a worktree "
            "(worktrees.sh add-branch <name>) and pass --repo <path>."
        )
    if args.scenario != "route" and SESSIONS_MISSING:
        sys.exit(
            f"this tree has no src.services.sessions package ({SESSIONS_MISSING}); "
            "layout and page need v0.8.3 or later, route works on any release"
        )
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    args.note = f"repo={args.repo.name} {args.note}".strip()

    if args.cold:
        subprocess.run([str(HERE / "bench.sh"), "restart"], check=True)
    if args.sql_before:
        with open(args.sql_before) as fh:
            psql(stdin=fh)
        psql("-c", "ANALYZE")
        args.note += f" sql_before={os.path.basename(args.sql_before)}"

    factory = sessionmaker(create_engine(Config.SQLALCHEMY_DATABASE_URI))
    with factory() as db:
        rec = Recorder(args, db)
    try:
        if args.scenario == "route":
            measure_routes(rec, factory, args.repeat, args.only)
        for sort in args.sort if args.scenario != "route" else []:
            if args.scenario == "layout":
                measure_layout(rec, factory, sort, args.builds)
            else:
                measure_pages(rec, factory, sort, args.repeat)
    finally:
        rec.finish()
        if args.sql_after:
            with open(args.sql_after) as fh:
                psql(stdin=fh)
    print(f"results: {args.csv} (run_id {rec.run_id}); next: just bench report")


if __name__ == "__main__":
    main()
