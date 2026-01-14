#!/usr/bin/env bash
set -euo pipefail

LP_DIR="${1:-}"                         # Directory containing .lp files (passed as first argument)

if [[ -z "$LP_DIR" ]]; then
  echo "Usage: $0 <directory_with_lp_files>"
  exit 2
fi

for lpfile in "$LP_DIR"/*.lp; do        # Iterate over all .lp files in the directory
  [[ -e "$lpfile" ]] || continue        # If no .lp files exist, avoid using the literal pattern
  outfile="${lpfile%.lp}.out"           # Output file path: same name, but with .out extension
  solfile="${lpfile%.lp}.sol"           # Temporary solution file written by Gurobi

  echo "Solving $lpfile"

  # Run Gurobi with parameters:
  #   LogFile=outfile, NonConvex=2, Presolve=0, Symmetry=0, TimeLimit=600
  # Write solution to solfile, then append it to outfile (so outfile contains log + solution)
  gurobi_cl \
    LogFile="$outfile" \
    ResultFile="$solfile" \
    NonConvex=2 \
    Presolve=0 \
    Symmetry=0 \
    TimeLimit=600 \
    "$lpfile"

  status=$?                             # Capture solver exit code

  if [[ $status -ne 0 ]]; then
    echo "❌ Error (exit code $status) for $lpfile"
    continue
  fi

  # Append solution to the same .out file (log + solution in one file)
  {
    echo
    echo "===== SOLUTION (from $solfile) ====="
    cat "$solfile"
    rm -f "$solfile"
  } >> "$outfile"

done
