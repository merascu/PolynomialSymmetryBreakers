#!/usr/bin/env python3

import csv
import os
import re
import sys

# Run
# python extract_to_csv_SMT2.py in_path="outputs" out_csv="results.csv"


USAGE = 'Usage: python extract_to_csv_SMT2.py in_path="outputs" out_csv="results.csv"'

TOTAL_TIME_PATTERN = re.compile(r":total-time\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
TIMEOUT_PATTERN = re.compile(r"\bTIMEOUT\s+after\s+([^\s,;.)\]]+)", re.IGNORECASE)


def parse_args(argv):
    args = {}

    for arg in argv[1:]:
        if "=" not in arg:
            raise ValueError(f"Invalid argument: {arg}. Expected key=value format. {USAGE}")

        key, value = arg.split("=", 1)
        args[key] = value.strip().strip('"').strip("'")

    missing = [key for key in ("in_path", "out_csv") if not args.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required argument(s): {joined}. {USAGE}")

    return args["in_path"], args["out_csv"]


def extract_time(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # First search for timeout and keep the duration found in the .out file.
    timeout_match = TIMEOUT_PATTERN.search(content)
    if timeout_match:
        return f"TIMEOUT after {timeout_match.group(1)}"

    # Then search for :total-time followed by a number.
    match = TOTAL_TIME_PATTERN.search(content)
    if match:
        return match.group(1)

    return ""


def main():
    try:
        in_path, out_csv = parse_args(sys.argv)

        if not os.path.isdir(in_path):
            raise NotADirectoryError(f"Input path is not a directory: {in_path}")

        rows = []

        for filename in sorted(os.listdir(in_path)):
            if not filename.endswith(".out"):
                continue

            file_path = os.path.join(in_path, filename)

            if not os.path.isfile(file_path):
                continue

            rows.append({
                "file": filename,
                "time_to_find_solution": extract_time(file_path),
            })

        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["file", "time_to_find_solution"],
            )
            writer.writeheader()
            writer.writerows(rows)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
