#!/usr/bin/env python3
"""
Extract SCIP results from one .out file or from all .out files in a directory.

Writes a CSV with one row per file:
  file,time,optimum_value

Required usage:
  python extract_to_csv_SCIP.py in_path="path/to/out_or_dir" out_csv="results.csv"

  - in_path: path to one .out file or to a directory containing .out files
  - out_csv: path to the CSV file to create

"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Optional


REQUIRED_ARGS = {"in_path", "out_csv"}
USAGE = 'Usage: python extract_to_csv_SCIP.py in_path="path/to/out_or_dir" out_csv="results.csv"'

STATUS_RE = re.compile(r"^SCIP Status\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
SOLVING_TIME_RE = re.compile(
    r"^Solving Time \(sec\)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
OBJ_VALUE_RE = re.compile(
    r"^objective value:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
PRIMAL_BOUND_RE = re.compile(
    r"^Primal Bound\s*:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    re.IGNORECASE | re.MULTILINE,
)

TIMEOUT_MARKERS = (
    "time limit reached",
    "timelimit",
    "time limit exceeded",
    "solving was interrupted",
)

OPTIMAL_MARKERS = (
    "optimal solution found",
    "problem is solved [optimal solution found]",
)


def first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def last_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    matches = pattern.findall(text)
    return matches[-1].strip() if matches else None


def parse_scip_log(path: Path) -> dict[str, str]:
    text = path.read_text(errors="replace")

    status = first_match(STATUS_RE, text) or "unknown"
    status_lower = status.lower()

    solving_time = first_match(SOLVING_TIME_RE, text)
    timed_out = any(marker in status_lower for marker in TIMEOUT_MARKERS)
    optimal = any(marker in status_lower for marker in OPTIMAL_MARKERS)

    # If no SCIP Status line exists, fall back to searching the full log text.
    if status == "unknown":
        text_lower = text.lower()
        timed_out = any(marker in text_lower for marker in TIMEOUT_MARKERS)
        optimal = any(marker in text_lower for marker in OPTIMAL_MARKERS)

    # Only write an optimum value when SCIP proved optimality.
    optimum_value = ""
    if optimal:
        optimum_value = last_match(OBJ_VALUE_RE, text) or first_match(PRIMAL_BOUND_RE, text) or ""

    return {
        "file": path.name,
        "time": "timeout" if timed_out else (solving_time or ""),
        "optimum_value": optimum_value,
    }


def parse_required_args(argv: list[str]) -> dict[str, str]:
    if len(argv) != 2:
        raise ValueError(
            f"Expected exactly 2 arguments: in_path=... and out_csv=...\n{USAGE}"
        )

    parsed: dict[str, str] = {}
    for item in argv:
        if "=" not in item:
            raise ValueError(f"Invalid argument {item!r}. Arguments must use key=value format.\n{USAGE}")

        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key not in REQUIRED_ARGS:
            raise ValueError(
                f"Unknown argument {key!r}. Only in_path=... and out_csv=... are allowed.\n{USAGE}"
            )
        if key in parsed:
            raise ValueError(f"Duplicate argument {key!r}.\n{USAGE}")
        if value == "":
            raise ValueError(f"Argument {key!r} cannot be empty.\n{USAGE}")

        parsed[key] = value

    missing = sorted(REQUIRED_ARGS - set(parsed))
    if missing:
        raise ValueError(f"Missing required argument(s): {', '.join(missing)}\n{USAGE}")

    return parsed


def collect_input_files(in_path: Path) -> list[Path]:
    if in_path.is_file():
        return [in_path]

    if not in_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist or is not a file/directory: {in_path}")

    return sorted(path for path in in_path.glob("*.out") if path.is_file())


def main() -> None:
    try:
        args = parse_required_args(sys.argv[1:])
        in_path = Path(args["in_path"])
        out_csv = Path(args["out_csv"])

        files = collect_input_files(in_path)
        rows = [parse_scip_log(path) for path in files]

        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "time", "optimum_value"])
            writer.writeheader()
            writer.writerows(rows)

        print(f"Wrote {len(rows)} rows to {out_csv}")

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
