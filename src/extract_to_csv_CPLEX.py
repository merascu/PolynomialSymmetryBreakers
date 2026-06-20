#!/usr/bin/env python3

import sys
import re
import csv
from pathlib import Path

#########################################################################################
#   python extract_to_csv_CPLEX.py in_path="path/to/out_or_dir" out_csv="results.csv" ####
#########################################################################################

# ---------------------- REGEX DEFINITIONS ----------------------

RE_OPT_STATUS = re.compile(r"MIP - Integer optimal solution", re.IGNORECASE)
RE_DET_LIMIT = re.compile(r"MIP - Deterministic time limit exceeded", re.IGNORECASE)

RE_OPT_OBJECTIVE = re.compile(
    r"MIP - Integer optimal solution:\s*Objective\s*=\s*([-\d.+eE]+)",
    re.IGNORECASE,
)

RE_CURR_BEST_BOUND_GAP = re.compile(
    r"Current MIP best bound\s*=\s*([-\d.+eE]+)\s*\(gap\s*=\s*([-\d.+eE]+)\s*,\s*([-\d.+eE]+)%\)",
    re.IGNORECASE,
)

RE_DET_TIME = re.compile(r"Deterministic time\s*=\s*([-\d.+eE]+)\s*ticks", re.IGNORECASE)

# Extract runtime + iterations + nodes ONLY from the summary line:
# "Solution time = ... sec.  Iterations = ...  Nodes = ..."
RE_SOLUTION_SUMMARY = re.compile(
    r"Solution time\s*=\s*([-\d.+eE]+)\s*sec\.\s*Iterations\s*=\s*(\d+)\s*Nodes\s*=\s*(\d+)",
    re.IGNORECASE,
)

RE_PROGRESS_HEADER = re.compile(r"^\s*Node\s+Left.*\bGap\b", re.IGNORECASE)
RE_PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)%")


# ---------------------- USAGE VALIDATION ----------------------

def usage_error():
    print(
        'Usage:\n'
        '  python parse_gurobi_out.py in_path="path/to/out_or_dir" out_csv="results.csv"',
        file=sys.stderr
    )
    sys.exit(1)


def parse_cli_arguments():
    if len(sys.argv) != 3:
        usage_error()

    args = {}
    for arg in sys.argv[1:]:
        if "=" not in arg:
            usage_error()

        key, value = arg.split("=", 1)

        if key not in ("in_path", "out_csv"):
            usage_error()

        if not value:
            usage_error()

        args[key] = value

    if set(args.keys()) != {"in_path", "out_csv"}:
        usage_error()

    return args["in_path"], args["out_csv"]


# ---------------------- PARSING HELPERS ----------------------

def read_text(path: Path):
    data = path.read_bytes().replace(b"\x00", b"")
    return data.decode("utf-8", errors="ignore").splitlines(keepends=True)


def extract_initial_gap(lines):
    header_idx = None
    for i, line in enumerate(lines):
        if RE_PROGRESS_HEADER.search(line):
            header_idx = i
            break

    if header_idx is None:
        return ""

    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue

        if line.lstrip().startswith(("Elapsed time", "MIP -", "Solution time", "CPLEX>")):
            break

        m = RE_PERCENT.search(line)
        if m:
            return f"{m.group(1)}%"

    return ""


def parse_out_file(path: Path):
    lines = read_text(path)
    text = "".join(lines)

    # (2) status
    status = ""
    if RE_DET_LIMIT.search(text):
        status = "MIP - Deterministic time limit exceeded"
    elif RE_OPT_STATUS.search(text):
        status = "MIP - Integer optimal solution"

    # (3) objective (only if optimal)
    objective = ""
    if status == "MIP - Integer optimal solution":
        m = RE_OPT_OBJECTIVE.search(text)
        if m:
            objective = m.group(1)

    # (4) gap from "Current MIP best bound ..." line (store %)
    gap = ""
    m = RE_CURR_BEST_BOUND_GAP.search(text)
    if m:
        gap = f"{m.group(3)}%"

    # (5) DeterministicTime (ticks)
    deterministic_time = ""
    m = RE_DET_TIME.search(text)
    if m:
        deterministic_time = m.group(1)

    # (6) runtime seconds, (8) simplex iters, (9) nodes explored
    runtime_seconds = ""
    simplex_iters = ""
    nodes_explored = ""

    m = RE_SOLUTION_SUMMARY.search(text)
    if m:
        runtime_seconds = m.group(1)
        simplex_iters = m.group(2)
        nodes_explored = m.group(3)

    # (7) initial gap from progress table
    initial_gap = extract_initial_gap(lines)

    return {
        "filename": path.name,
        "status": status,
        "objective": objective,
        "gap": gap,
        "DeterministicTime": deterministic_time,
        "runtime_seconds": runtime_seconds,
        "initial_gap": initial_gap,
        "simplex_iters": simplex_iters,
        "nodes_explored": nodes_explored,
    }


# ---------------------- MAIN ----------------------

def main():
    in_path_str, out_csv_str = parse_cli_arguments()

    in_path = Path(in_path_str)
    if not in_path.exists():
        print(f"Error: in_path does not exist: {in_path}", file=sys.stderr)
        sys.exit(1)

    if in_path.is_file():
        if in_path.suffix.lower() != ".out":
            print("Error: input file must have .out extension", file=sys.stderr)
            sys.exit(1)
        out_files = [in_path]
    else:
        out_files = sorted(in_path.glob("*.out"))

    if not out_files:
        print("Error: no .out files found", file=sys.stderr)
        sys.exit(1)

    rows = [parse_out_file(p) for p in out_files]

    fieldnames = [
        "filename",
        "status",
        "objective",
        "gap",
        "DeterministicTime",
        "runtime_seconds",
        "initial_gap",
        "simplex_iters",
        "nodes_explored",
    ]

    with open(out_csv_str, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()