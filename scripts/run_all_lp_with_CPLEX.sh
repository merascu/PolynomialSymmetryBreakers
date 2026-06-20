#!/usr/bin/env bash
# +-----------+----------+----------+----------+------------+-----------------+-------------------+----------------------+
# | Parameter | Baseline | Default | Moderate | Aggressive | Very aggressive | Highly aggressive | extremely aggressive |
# +-----------+----------+----------+----------+------------+--------- -------+-------------------+----------------------+
# | Presolve  |    no     |    1    |     1    |     1      |         1       |       1           |        1             |
# | Symmetry  |    0     |   -1    |     1    |     2      |         3       |       4           |        5             |
# +-----------+----------+----------+----------+------------+-----------------+-------------------+----------------------+
# set preprocessing presolve no
# set preprocessing symmetry 0
# set dettimelimit 1000000 in the case we did not use our sbs
# set dettimelimit 2000000 in the case we did use our sbs because the previous was too small
# set dettimelimit 9000000 - too long to wait for the tests

#!/usr/bin/env bash
set -euo pipefail

LP_DIR="${1:-}"
if [[ -z "$LP_DIR" ]]; then
  echo "Usage: $0 <directory_with_lp_files>"
  exit 2
fi

CPLEX_CMD="${CPLEX_CMD:-/Applications/CPLEX_Studio2211/cplex/bin/arm64_osx/cplex}"

for lpfile in "$LP_DIR"/*.lp; do
  [[ -e "$lpfile" ]] || continue

  outfile="${lpfile%.lp}.out"
  solfile="${lpfile%.lp}.sol"

  echo "Solving $lpfile"

  set +e
  "$CPLEX_CMD" >"$outfile" 2>&1 <<EOF
read "$lpfile"
set preprocessing presolve no
set preprocessing symmetry 0
set dettimelimit 2000000
optimize
write "$solfile"
quit
EOF
  status=$?
  set -e

  if [[ $status -ne 0 ]]; then
    echo "❌ Error (exit code $status) for $lpfile"
    continue
  fi

  {
    echo
    echo "===== SOLUTION (from $solfile) ====="
    if [[ -f "$solfile" ]]; then
      cat "$solfile"
      rm -f "$solfile"
    else
      echo "(No .sol file produced by CPLEX.)"
    fi
  } >>"$outfile"
done




