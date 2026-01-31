#!/usr/bin/env python3
"""
parse_gurobi_out.py

Run:
  python parse_gurobi_out.py in_path="path/to/out_or_dir" out_csv="results.csv"

Extract:
(1) filename
(2) status: "Time limit reached" if present, else "Optimal solution found" if present, else empty
(3) objective: value of "Best objective" ONLY when on the same line you also have "gap 0.0000%"
(4) gap: from the line "Best objective ..., best bound ..., gap ...%"
(5) work units: from the line "Explored ... ( ... work units)"
(6) runtime (seconds): from the same "Explored ..." line
(7) initial gap: from the first nonempty progress-table row after the header
(8) simplex iters: from the "Explored ..." line
(9) nodes explored: from the "Explored ..." line
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, List


REQUIRED_KEYS = ("in_path", "out_csv")


def usage(prog: str) -> str:
    return f'python {prog} in_path="path/to/out_or_dir" out_csv="results.csv"'


def parse_kv_args(argv: List[str]) -> Dict[str, str]:
    prog = os.path.basename(argv[0])
    args = argv[1:]

    if len(args) == 1 and args[0] in ("-h", "--help"):
        print(usage(prog))
        sys.exit(0)

    kv: Dict[str, str] = {}
    for tok in args:
        if "=" not in tok:
            raise SystemExit(f"Error: expected key=value, got '{tok}'.\nUsage: {usage(prog)}")
        k, v = tok.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not k:
            raise SystemExit(f"Error: empty key in '{tok}'.\nUsage: {usage(prog)}")
        if k in kv:
            raise SystemExit(f"Error: duplicate argument '{k}'.\nUsage: {usage(prog)}")
        kv[k] = v

    missing = [k for k in REQUIRED_KEYS if k not in kv or kv[k] == ""]
    if missing:
        raise SystemExit(f"Error: missing mandatory arguments: {', '.join(missing)}.\nUsage: {usage(prog)}")

    unknown = [k for k in kv.keys() if k not in REQUIRED_KEYS]
    if unknown:
        raise SystemExit(
            f"Error: unknown argument(s): {', '.join(unknown)}.\n"
            f"Allowed: {', '.join(REQUIRED_KEYS)}\n"
            f"Usage: {usage(prog)}"
        )
    return kv


# Compiled once (fast)
RE_TIME_LIMIT = re.compile(r"\bTime limit reached\b")
RE_OPTIMAL = re.compile(r"\bOptimal solution found\b")

RE_BEST_LINE = re.compile(
    r"Best objective\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?),\s*best bound\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?),\s*gap\s+([0-9]*\.?[0-9]+)%",
    re.IGNORECASE,
)

RE_EXPLORED = re.compile(
    r"Explored\s+(\d+)\s+nodes?\s*\(\s*(\d+)\s+simplex iterations\s*\)\s+in\s+([0-9]*\.?[0-9]+)\s+seconds\s*\(\s*([0-9]*\.?[0-9]+)\s+work units\s*\)",
    re.IGNORECASE,
)

RE_TABLE_HEADER = re.compile(
    r"Expl\s+Unexpl.*Incumbent\s+BestBd\s+Gap.*It/Node\s+Time",
    re.IGNORECASE,
)

RE_PROGRESS_ROW_START = re.compile(r"^(H\s+)?\d+\s+\d+\s+")
RE_PERCENT = re.compile(r"([0-9]*\.?[0-9]+%)")


def iter_out_files(in_path: Path) -> Iterator[Path]:
    if in_path.is_file():
        yield in_path
        return
    if not in_path.is_dir():
        raise SystemExit(f"Error: in_path not found: {in_path}")

    # os.scandir is faster than Path.glob for huge directories
    with os.scandir(in_path) as it:
        for entry in it:
            if entry.is_file() and entry.name.endswith(".out"):
                yield Path(entry.path)


def parse_out_file_stream(path: Path) -> Dict[str, str]:
    status = ""
    best_obj = ""
    gap = ""
    nodes = ""
    simplex_iters = ""
    runtime = ""
    work_units = ""
    initial_gap = ""

    saw_table_header = False
    captured_initial_gap = False

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            # status (time limit takes precedence)
            if status != "Time limit reached":
                if RE_TIME_LIMIT.search(ln):
                    status = "Time limit reached"
                elif not status and RE_OPTIMAL.search(ln):
                    status = "Optimal solution found"

            # best objective / gap (take last occurrence)
            m = RE_BEST_LINE.search(ln)
            if m:
                obj_str = m.group(1)
                gap_str = m.group(3)
                gap = f"{gap_str}%"
                best_obj = obj_str if gap_str == "0.0000" else ""

            # explored stats (take last occurrence)
            m = RE_EXPLORED.search(ln)
            if m:
                nodes = m.group(1)
                simplex_iters = m.group(2)
                runtime = m.group(3)
                work_units = m.group(4)

            # initial gap: detect table header then first data row after it
            if not captured_initial_gap:
                if not saw_table_header:
                    if RE_TABLE_HEADER.search(ln):
                        saw_table_header = True
                    continue
                else:
                    s = ln.strip()
                    if not s:
                        continue
                    # skip separator lines
                    stripped = s.replace("|", "").replace("-", "").replace("=", "").strip()
                    if stripped == "":
                        continue
                    # first real progress row (space-separated in your logs)
                    if not RE_PROGRESS_ROW_START.match(s):
                        continue
                    # gap column appears as a percent in the row; take the last percent token
                    percents = RE_PERCENT.findall(s)
                    if percents:
                        initial_gap = percents[-1]
                    else:
                        initial_gap = ""
                    captured_initial_gap = True

    return {
        "filename": path.name,
        "status": status,
        "objective": best_obj,
        "gap": gap,
        "work_units": work_units,
        "runtime_seconds": runtime,
        "initial_gap": initial_gap,
        "simplex_iters": simplex_iters,
        "nodes": nodes,
    }


def main() -> None:
    kv = parse_kv_args(sys.argv)
    in_path = Path(kv["in_path"])
    out_csv = Path(kv["out_csv"])

    files = list(iter_out_files(in_path))
    if not files:
        raise SystemExit(f"Error: no .out files found in: {in_path}")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "filename",
        "status",
        "objective",
        "gap",
        "work_units",
        "runtime_seconds",
        "initial_gap",
        "simplex_iters",
        "nodes",
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in files:
            w.writerow(parse_out_file_stream(p))

    print(f"Wrote CSV: {out_csv} ({len(files)} file(s))")


if __name__ == "__main__":
    main()