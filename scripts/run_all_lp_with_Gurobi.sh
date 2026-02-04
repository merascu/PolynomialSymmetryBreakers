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

  Table: Gurobi configurations used in our experiments

#+-----------+----------+---------+--------------+------------+
#| Parameter | Baseline | Default | Conservative | Aggressive |
#+-----------+----------+---------+--------------+------------+
#| Nonconvex |    2     |    2    |      2       |     2      |
#| Presolve  |    0     |   -1    |     -1       |    -1      |
#| Symmetry  |    0     |   -1    |      1       |     2      |
#+-----------+----------+---------+--------------+------------+

#   Run Gurobi with parameters:
#   LogFile=outfile,
#   NonConvex=2 -- Sets the strategy for handling non-convex quadratic objectives or non-convex
#   quadratic constraints
#   (see https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html).               #
#   Presolve=0 (disabled),
#   Symmetry=0,
#   WorkLimit=1800
#   NonConvex=2: # Write solution to solfile, then append it to outfile (so outfile contains log + solution)
  gurobi_cl \
    LogFile="$outfile" \
    ResultFile="$solfile" \
    NonConvex=2 \
    Presolve=0 \
    Symmetry=0 \
    WorkLimit=1800 \
    "$lpfile"

# Presolve - default (-1)
# Symmetry - default (A value of -1 corresponds to an automatic setting; Default settings are quite effective, so changing the value of this parameter rarely produces a significant benefit.)
#gurobi_cl \
#    LogFile="$outfile" \
#    ResultFile="$solfile" \
#    NonConvex=2 \
#    WorkLimit=1800 \
#    "$lpfile"

# Presolve - default (-1)
# Symmetry = 1 conservative
#  gurobi_cl \
#    LogFile="$outfile" \
#    ResultFile="$solfile" \
#    NonConvex=2 \
#    Symmetry=1 \
#    WorkLimit=1800 \
#    "$lpfile"

## Presolve - default (-1)
## Symmetry = 2 aggresive
#  gurobi_cl \
#    LogFile="$outfile" \
#    ResultFile="$solfile" \
#    NonConvex=2 \
#    Symmetry=2 \
#    WorkLimit=1800 \
#    "$lpfile"



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
