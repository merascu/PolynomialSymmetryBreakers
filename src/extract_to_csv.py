#!/usr/bin/env python3
"""Extract (file name, work time, runtime, optimum) from solver log files.

What it extracts
- Work time + runtime from lines like:
  "Explored 1 nodes (3672 simplex iterations) in 0.44 seconds (0.84 work units)"
  -> runtime = 0.44, work_time = 0.84

- Optimum only for files that contain "Optimal solution found". Then, within the next
  few lines, a line like:
  "Best objective 1.500000000000e+02, best bound ..."
  -> optimum = 1.500000000000e+02

If a value cannot be found, the corresponding CSV cell is left blank.

Usage examples
  # Parse all files in a directory
  python extract_solver_metrics.py /path/to/logs /path/to/output.csv

  # Only parse .out files
  python extract_solver_metrics.py /path/to/logs /path/to/output.csv --glob "*.out"
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

EXPLORED_RE = re.compile(
    r"Explored\s+\d+\s+nodes\s+\(.*?simplex iterations\)\s+in\s+([0-9]*\.?[0-9]+)\s+seconds\s+\(([0-9]*\.?[0-9]+)\s+work units\)",
    re.IGNORECASE,
)

BEST_OBJ_RE = re.compile(
    r"Best\s+objective\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][+-]?\d+)?)",
    re.IGNORECASE,
)


def extract_from_text(text: str) -> dict[str, str | None]:
    runtime: str | None = None
    work_time: str | None = None
    optimum: str | None = None

    # lines remaining to look for Best objective after "Optimal solution found"
    expect_best_obj = 0

    for line in text.splitlines():
        m = EXPLORED_RE.search(line)
        if m:
            # Keep the *last* occurrence; it's typically the final summary.
            runtime = m.group(1)
            work_time = m.group(2)

        if "Optimal solution found" in line:
            expect_best_obj = 6  # tolerate blank/comment lines
            continue

        if expect_best_obj > 0:
            m2 = BEST_OBJ_RE.search(line)
            if m2:
                optimum = m2.group(1)
                expect_best_obj = 0
            else:
                expect_best_obj -= 1

    return {"runtime": runtime, "work_time": work_time, "optimum": optimum}


def iter_files(dir_path: Path, glob_pat: str):
    # Use rglob so it works recursively.
    for p in sorted(dir_path.rglob(glob_pat)):
        if p.is_file():
            yield p


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract solver metrics from many log files into a CSV.")
    parser.add_argument("directory", help="Directory that contains the log/output files")
    parser.add_argument("output_csv", help="Path to write the CSV")
    parser.add_argument(
        "--glob",
        default="*",
        help='Which files to parse (glob pattern, recursive). Example: "*.out" or "*.log". Default: *',
    )

    args = parser.parse_args(argv[1:])

    in_dir = Path(args.directory).expanduser().resolve()
    out_csv = Path(args.output_csv).expanduser().resolve()

    if not in_dir.exists() or not in_dir.is_dir():
        print(f"Error: directory not found: {in_dir}", file=sys.stderr)
        return 2

    rows = []
    for f in iter_files(in_dir, args.glob):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"Warning: could not read {f}: {e}", file=sys.stderr)
            continue

        metrics = extract_from_text(text)
        rows.append(
            {
                "file": f.name,
                "work_time": metrics["work_time"] or "",
                "runtime": metrics["runtime"] or "",
                "optimum": metrics["optimum"] or "",
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["file", "work_time", "runtime", "optimum"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))