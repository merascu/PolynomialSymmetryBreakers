#!/usr/bin/env python3
"""Extract CPLEX, Gurobi, SCIP, or SMT2 results from .out files into CSV.

Usage:
    python extract_to_csv.py in_path="path/to/out_or_dir" out_csv="results.csv" solver="solver"

Supported solvers: cplex, gurobi, scip, smt2
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Callable


# CPLEX patterns
CPLEX_OPT_STATUS = re.compile(r"MIP - Integer optimal solution", re.IGNORECASE)
CPLEX_TIME_LIMIT = re.compile(r"MIP - Deterministic time limit exceeded", re.IGNORECASE)
CPLEX_OBJECTIVE = re.compile(
    r"MIP - Integer optimal solution:\s*Objective\s*=\s*([-\d.+eE]+)", re.IGNORECASE
)
CPLEX_BOUND_GAP = re.compile(
    r"Current MIP best bound\s*=\s*([-\d.+eE]+)\s*"
    r"\(gap\s*=\s*([-\d.+eE]+)\s*,\s*([-\d.+eE]+)%\)",
    re.IGNORECASE,
)
CPLEX_DET_TIME = re.compile(
    r"Deterministic time\s*=\s*([-\d.+eE]+)\s*ticks", re.IGNORECASE
)
CPLEX_SUMMARY = re.compile(
    r"Solution time\s*=\s*([-\d.+eE]+)\s*sec\.\s*"
    r"Iterations\s*=\s*(\d+)\s*Nodes\s*=\s*(\d+)",
    re.IGNORECASE,
)
CPLEX_HEADER = re.compile(r"^\s*Node\s+Left.*\bGap\b", re.IGNORECASE)
PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)%")

# Gurobi patterns
GUROBI_TIME_LIMIT = re.compile(r"\bTime limit reached\b", re.IGNORECASE)
GUROBI_OPTIMAL = re.compile(r"\bOptimal solution found\b", re.IGNORECASE)
GUROBI_BEST = re.compile(
    r"Best objective\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?),\s*"
    r"best bound\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?),\s*"
    r"gap\s+([0-9]*\.?[0-9]+)%",
    re.IGNORECASE,
)
GUROBI_EXPLORED = re.compile(
    r"Explored\s+(\d+)\s+nodes?\s*\(\s*(\d+)\s+simplex iterations\s*\)\s*"
    r"in\s+([0-9]*\.?[0-9]+)\s+seconds\s*\(\s*"
    r"([0-9]*\.?[0-9]+)\s+work units\s*\)",
    re.IGNORECASE,
)
GUROBI_HEADER = re.compile(
    r"Expl\s+Unexpl.*Incumbent\s+BestBd\s+Gap.*It/Node\s+Time", re.IGNORECASE
)
GUROBI_ROW = re.compile(r"^(H\s+)?\d+\s+\d+\s+")
GUROBI_PERCENT = re.compile(r"([0-9]*\.?[0-9]+%)")

# SCIP patterns
SCIP_STATUS = re.compile(r"^SCIP Status\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
SCIP_TIME = re.compile(
    r"^Solving Time \(sec\)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SCIP_OBJECTIVE = re.compile(
    r"^objective value:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SCIP_PRIMAL_BOUND = re.compile(
    r"^Primal Bound\s*:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    re.IGNORECASE | re.MULTILINE,
)
SCIP_TIMEOUT_MARKERS = (
    "time limit reached",
    "timelimit",
    "time limit exceeded",
    "solving was interrupted",
)
SCIP_OPTIMAL_MARKERS = (
    "optimal solution found",
    "problem is solved [optimal solution found]",
)

# SMT2 patterns
SMT2_TOTAL_TIME = re.compile(r":total-time\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
SMT2_TIMEOUT = re.compile(r"\bTIMEOUT\s+after\s+([^\s,;.)\]]+)", re.IGNORECASE)


def read_text(path: Path) -> str:
    """Read a log while tolerating invalid bytes and embedded NUL characters."""
    return path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="replace")


def first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def last_match(pattern: re.Pattern[str], text: str) -> str:
    matches = pattern.findall(text)
    return matches[-1].strip() if matches else ""


def parse_cplex(path: Path) -> dict[str, str]:
    text = read_text(path)
    lines = text.splitlines()

    status = ""
    if CPLEX_TIME_LIMIT.search(text):
        status = "MIP - Deterministic time limit exceeded"
    elif CPLEX_OPT_STATUS.search(text):
        status = "MIP - Integer optimal solution"

    objective = ""
    if status == "MIP - Integer optimal solution":
        objective = first_match(CPLEX_OBJECTIVE, text)

    gap_match = CPLEX_BOUND_GAP.search(text)
    summary_match = CPLEX_SUMMARY.search(text)

    initial_gap = ""
    after_header = False
    for line in lines:
        if not after_header:
            after_header = bool(CPLEX_HEADER.search(line))
            continue
        if not line.strip():
            continue
        if line.lstrip().startswith(("Elapsed time", "MIP -", "Solution time", "CPLEX>")):
            break
        match = PERCENT.search(line)
        if match:
            initial_gap = f"{match.group(1)}%"
            break

    return {
        "filename": path.name,
        "status": status,
        "objective": objective,
        "gap": f"{gap_match.group(3)}%" if gap_match else "",
        "DeterministicTime": first_match(CPLEX_DET_TIME, text),
        "runtime_seconds": summary_match.group(1) if summary_match else "",
        "initial_gap": initial_gap,
        "simplex_iters": summary_match.group(2) if summary_match else "",
        "nodes_explored": summary_match.group(3) if summary_match else "",
    }


def parse_gurobi(path: Path) -> dict[str, str]:
    status = ""
    objective = ""
    gap = ""
    work_units = ""
    runtime = ""
    initial_gap = ""
    simplex_iters = ""
    nodes = ""
    after_header = False

    for line in read_text(path).splitlines():
        if status != "Time limit reached":
            if GUROBI_TIME_LIMIT.search(line):
                status = "Time limit reached"
            elif not status and GUROBI_OPTIMAL.search(line):
                status = "Optimal solution found"

        match = GUROBI_BEST.search(line)
        if match:
            gap_value = match.group(3)
            gap = f"{gap_value}%"
            objective = match.group(1) if gap_value == "0.0000" else ""

        match = GUROBI_EXPLORED.search(line)
        if match:
            nodes, simplex_iters, runtime, work_units = match.groups()

        if not initial_gap:
            if not after_header:
                after_header = bool(GUROBI_HEADER.search(line))
            else:
                stripped = line.strip()
                if stripped and GUROBI_ROW.match(stripped):
                    percentages = GUROBI_PERCENT.findall(stripped)
                    initial_gap = percentages[-1] if percentages else ""

    return {
        "filename": path.name,
        "status": status,
        "objective": objective,
        "gap": gap,
        "work_units": work_units,
        "runtime_seconds": runtime,
        "initial_gap": initial_gap,
        "simplex_iters": simplex_iters,
        "nodes": nodes,
    }


def parse_scip(path: Path) -> dict[str, str]:
    text = read_text(path)
    status = first_match(SCIP_STATUS, text) or "unknown"
    searchable = text.lower() if status == "unknown" else status.lower()
    timed_out = any(marker in searchable for marker in SCIP_TIMEOUT_MARKERS)
    optimal = any(marker in searchable for marker in SCIP_OPTIMAL_MARKERS)

    objective = ""
    if optimal:
        objective = last_match(SCIP_OBJECTIVE, text) or first_match(SCIP_PRIMAL_BOUND, text)

    return {
        "file": path.name,
        "time": "timeout" if timed_out else first_match(SCIP_TIME, text),
        "optimum_value": objective,
    }


def parse_smt2(path: Path) -> dict[str, str]:
    text = read_text(path)
    timeout = SMT2_TIMEOUT.search(text)
    total_time = SMT2_TOTAL_TIME.search(text)
    value = f"TIMEOUT after {timeout.group(1)}" if timeout else (total_time.group(1) if total_time else "")
    return {"file": path.name, "time_to_find_solution": value}


PARSERS: dict[str, tuple[Callable[[Path], dict[str, str]], list[str]]] = {
    "cplex": (
        parse_cplex,
        [
            "filename",
            "status",
            "objective",
            "gap",
            "DeterministicTime",
            "runtime_seconds",
            "initial_gap",
            "simplex_iters",
            "nodes_explored",
        ],
    ),
    "gurobi": (
        parse_gurobi,
        [
            "filename",
            "status",
            "objective",
            "gap",
            "work_units",
            "runtime_seconds",
            "initial_gap",
            "simplex_iters",
            "nodes",
        ],
    ),
    "scip": (parse_scip, ["file", "time", "optimum_value"]),
    "smt2": (parse_smt2, ["file", "time_to_find_solution"]),
}


def key_value_arguments(arguments: list[str]) -> list[str]:
    """Convert key=value arguments to argparse's --key=value form."""
    converted = []
    for argument in arguments:
        if argument in ("-h", "--help"):
            converted.append(argument)
        elif "=" in argument and not argument.startswith("--"):
            converted.append(f"--{argument}")
        else:
            converted.append(argument)
    return converted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract solver results from one .out file or a directory of .out files.",
        allow_abbrev=False,
    )
    parser.add_argument("--in_path", required=True, help="input .out file or directory")
    parser.add_argument("--out_csv", required=True, help="CSV file to create")
    parser.add_argument(
        "--solver",
        type=str.lower,
        choices=PARSERS,
        required=True,
        help="solver format: cplex, gurobi, scip, or smt2",
    )
    return parser.parse_args()

def collect_out_files(in_path: Path) -> list[Path]:
    if in_path.is_file():
        if in_path.suffix.lower() != ".out":
            raise ValueError("input file must have a .out extension")
        return [in_path]
    if not in_path.is_dir():
        raise FileNotFoundError(f"input path does not exist: {in_path}")
    return sorted(path for path in in_path.glob("*.out") if path.is_file())


def main() -> None:
    args = parse_args()
    in_path = Path(args.in_path)
    out_csv = Path(args.out_csv)
    parser, fieldnames = PARSERS[args.solver]

    files = collect_out_files(in_path)
    if not files:
        raise SystemExit(f"Error: no .out files found in: {in_path}")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parser(path) for path in files)

    print(f"Wrote {len(files)} row(s) to {out_csv}")


if __name__ == "__main__":
    main()
