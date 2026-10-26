#!/usr/bin/env python3
"""Render the results CSV as a markdown table.

Each row is the median of the measured runs of one scenario, sort, label and
variant, with the change against the baseline variant. A layout build 0 is a
warm-up and is dropped.

    summarize.py                          print the table
    summarize.py --append                 also append it to bench/RESULTS.md
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
    "scenario", "sort", "label", "variant", "n", "cpu_ms (median)", "vs baseline",
    "wall_ms (median)", "wall min-max", "read_MB", "fingerprint",
]  # fmt: skip


def median(values: list[str]) -> float | None:
    numbers = [float(v) for v in values if v != ""]
    return st.median(numbers) if numbers else None


def line(cells: Sequence[object]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="results CSV to read")
    ap.add_argument("--append", action="store_true", help="append to bench/RESULTS.md")
    args = ap.parse_args()

    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    with open(args.csv, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["scenario"] == "layout" and r["build_idx"] == "0":
                continue
            groups[(r["scenario"], r["sort"], r["label"], r["variant"])].append(r)

    out = [line(COLUMNS), line(["---"] * len(COLUMNS))]
    order = sorted(groups, key=lambda k: (*k[:3], k[3] != "baseline", k[3]))
    for key in order:
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
        matches = {r["fp_match_baseline"] for r in g}
        fp = (
            "same as baseline" if matches == {"True"}
            else "DIFFERS" if "False" in matches
            else "-"
        )  # fmt: skip
        out.append(
            line(
                [
                    scenario,
                    sort,
                    label,
                    variant,
                    len(g),
                    "" if cpu is None else cpu,
                    delta,
                    f"{st.median(walls):.0f}",
                    f"{min(walls):.0f}-{max(walls):.0f}",
                    median([r["read_mb"] for r in g]) or "",
                    fp,
                ]
            )  # fmt: skip
        )

    table = "\n".join(out)
    print(table)
    if args.append:
        stamp = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
        heading = f"### Generated summary {stamp} ({pathlib.Path(args.csv).name})"
        with OUT.open("a") as fh:
            fh.write(f"\n\n{heading}\n\n{table}\n")
        print(f"\nappended to {OUT}")


if __name__ == "__main__":
    main()
