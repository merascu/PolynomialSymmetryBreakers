#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./outs_to_csv.sh /path/to/out_dir results.csv
#
# Output CSV columns:
#   file,optimal_value,runtime_seconds
#
# Rules:
# - optimal_value is reported ONLY if the file contains "Optimal solution found"
# - in that case, optimal_value is read from "# Objective value = ..."
# - otherwise optimal_value is blank
# - runtime is taken from last:
#     - "Explored ... in X seconds" (MIP)
#     - or "Solved in X seconds" (LP)

OUT_DIR="${1:-}"
CSV_OUT="${2:-results.csv}"

if [[ -z "$OUT_DIR" ]]; then
  echo "Usage: $0 <out_dir> [output.csv]" >&2
  exit 2
fi
if [[ ! -d "$OUT_DIR" ]]; then
  echo "Error: not a directory: $OUT_DIR" >&2
  exit 2
fi

printf "file,optimal_value,runtime_seconds\n" > "$CSV_OUT"

shopt -s nullglob
for f in "$OUT_DIR"/*.out; do
  base="$(basename "$f")"

  # --- runtime (seconds) ---
  runtime="$(
    awk '
      # MIP line example:
      # Explored ... in 413.67 seconds (810.93 work units)
      /^Explored .* in [0-9.]+ seconds/ {
        for (i=1; i<=NF; i++) if ($i=="in") explored=$(i+1)
      }

      # LP line example:
      # Solved in 0.84 seconds (0.02 work units)
      /^Solved in [0-9.]+ seconds/ { solved=$3 }

      END {
        if (explored!="") print explored;
        else if (solved!="") print solved;
        else print "";
      }
    ' "$f"
  )"

  # --- optimal value: ONLY if "Optimal solution found" exists ---
  optimal_value=""
  if grep -q "Optimal solution found" "$f"; then
    # Extract last "# Objective value = <number>" (from appended solution section)
    optimal_value="$(
      awk -F'=' '
        /^\# Objective value[[:space:]]*=/ {
          val=$2
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
          last=val
        }
        END { if (last!="") print last; else print "" }
      ' "$f"
    )"
  fi

  printf "%s,%s,%s\n" "$base" "$optimal_value" "$runtime" >> "$CSV_OUT"
done

echo "Wrote: $CSV_OUT"
