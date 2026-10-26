#!/usr/bin/env python3
"""Show the results CSV as a table: median per request, change against the baseline.

A row groups the measured runs of one scenario, sort, label and variant. Layout
build 0 is a warm-up and is dropped. cpu_ms is the database container's CPU, app_ms
the benchmark process's own CPU (routing, serialization), wall_ms the whole call.

    summarize.py                       aligned text, grouped by scenario
    summarize.py --rank wall           slowest first across everything
    summarize.py --scenario route      one scenario only
    summarize.py --md --append         markdown, also appended to bench/RESULTS.md
    summarize.py --csv results/other.csv

Standard library only. Every number is computed from the CSV; none is typed in.
"""

import argparse
import csv
import datetime as dt
import pathlib
import statistics as st
from collections import defaultdict
from collections.abc import Sequence

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CSV = HERE / "results" / "results.csv"
OUT = HERE / "RESULTS.md"
COLUMNS = [
    "scenario", "sort", "label", "variant", "n", "cpu_ms", "vs baseline",
    "app_ms", "wall_ms", "wall min-max", "KB", "check",
]  # fmt: skip
TEXT_COLUMNS = 4  # left-aligned, the rest are numbers
LABEL_WIDTH = 72


def median(values: list[str]) -> float | None:
    numbers = [float(v) for v in values if v != ""]
    return st.median(numbers) if numbers else None


def fmt(value: float | None, digits: int = 0) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def md_line(cells: Sequence[object]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def aligned(table: list[list[str]]) -> str:
    widths = [max(len(r[i]) for r in table) for i in range(len(COLUMNS))]
    out = []
    for n, row in enumerate(table):
        cells = [
            c.ljust(w) if i < TEXT_COLUMNS else c.rjust(w)
            for i, (c, w) in enumerate(zip(row, widths, strict=True))
        ]
        out.append("  ".join(cells).rstrip())
        if n == 0:
            out.append("  ".join("-" * w for w in widths))
    return "\n".join(out)


def check(group: list[dict[str, str]]) -> str:
    """HTTP errors first, then whether the output still matches the baseline."""
    codes = {r["status"] for r in group if r.get("status")} - {"200"}
    if codes:
        return "HTTP " + ",".join(sorted(codes))
    matches = {r["fp_match_baseline"] for r in group}
    if "False" in matches:
        return "DIFFERS"
    return "same" if matches == {"True"} else "-"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="results CSV to read")
    ap.add_argument("--scenario", help="only this scenario (route, layout, page)")
    ap.add_argument(
        "--rank", choices=["cpu", "app", "wall", "kb"], help="slowest first"
    )
    ap.add_argument(
        "--md", action="store_true", help="markdown instead of aligned text"
    )
    ap.add_argument(
        "--append", action="store_true", help="markdown, also appended to RESULTS.md"
    )
    args = ap.parse_args()

    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    with open(args.csv, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["scenario"] == "layout" and r["build_idx"] == "0":
                continue
            if args.scenario and r["scenario"] != args.scenario:
                continue
            groups[(r["scenario"], r["sort"], r["label"], r["variant"])].append(r)

    records = []
    for key in sorted(groups, key=lambda k: (*k[:3], k[3] != "baseline", k[3])):
        scenario, sort, label, variant = key
        g = groups[key]
        cpu = median([r["cpu_ms"] for r in g])
        base = groups.get((scenario, sort, label, "baseline"))
        base_cpu = median([r["cpu_ms"] for r in base]) if base else None
        if variant == "baseline":
            delta = "-"
        elif cpu is not None and base_cpu:
            delta = f"{(cpu - base_cpu) / base_cpu * 100:+.1f}%"
        else:
            delta = "n/a"
        walls = [float(r["wall_ms"]) for r in g]
        size = median([r.get("bytes", "") for r in g])
        shown = label if len(label) <= LABEL_WIDTH else label[: LABEL_WIDTH - 3] + "..."
        app = median([r.get("app_cpu_ms", "") for r in g])
        rank = {"cpu": cpu, "app": app, "wall": st.median(walls),
                "kb": size}  # fmt: skip
        records.append((rank.get(args.rank) or 0, [
            scenario, sort, shown, variant, str(len(g)), fmt(cpu), delta,
            fmt(app), fmt(st.median(walls)),
            f"{min(walls):.0f}-{max(walls):.0f}",
            fmt(None if size is None else size / 1024, 1), check(g),
        ]))  # fmt: skip
    if args.rank:
        records.sort(key=lambda x: -x[0])

    rows = [r for _, r in records]
    markdown = args.md or args.append
    if markdown:
        table = "\n".join(
            [md_line(COLUMNS), md_line(["---"] * len(COLUMNS)), *map(md_line, rows)]
        )
    else:
        table = aligned([COLUMNS, *rows])
    print(table)
    if args.append:
        stamp = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
        heading = f"### Generated summary {stamp} ({pathlib.Path(args.csv).name})"
        with OUT.open("a") as fh:
            fh.write(f"\n\n{heading}\n\n{table}\n")
        print(f"\nappended to {OUT}")


if __name__ == "__main__":
    main()
