#!/usr/bin/env bash
set -euo pipefail

BREW_PREFIX="$(brew --prefix)"
SCIP_BIN="${SCIP_BIN:-$BREW_PREFIX/bin/scip}"   # override with SCIP_BIN=/full/path/to/scip
LP_DIR="${1:-}"                                 # directory containing .lp files

if [[ -z "$LP_DIR" ]]; then
  echo "Usage: $0 <directory_with_lp_files>"
  exit 2
fi

if [[ ! -x "$SCIP_BIN" ]]; then
  echo "Error: SCIP executable '$SCIP_BIN' not found or not executable"
  echo "Try:"
  echo "  brew install scip"
  echo "or run with:"
  echo "  SCIP_BIN=/full/path/to/scip $0 <directory_with_lp_files>"
  exit 127
fi

shopt -s nullglob

files=("$LP_DIR"/*.lp)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "No .lp files found in: $LP_DIR"
  exit 1
fi

for lpfile in "${files[@]}"; do
  outfile="${lpfile%.lp}.out"    # log file
  solfile="${lpfile%.lp}.sol"    # temporary SCIP solution file
  cmdfile="$(mktemp "${TMPDIR:-/tmp}/scip_cmds.XXXXXX")"

  echo "Solving $lpfile"
  echo "Writing log to $outfile"

  cat > "$cmdfile" <<EOF
read $lpfile
set limits time 1800
optimize
write solution $solfile
quit
EOF

  set +e
  "$SCIP_BIN" -l "$outfile" -b "$cmdfile"
  status=$?
  set -e

  rm -f "$cmdfile"

  if [[ $status -ne 0 ]]; then
    echo "Error (exit code $status) for $lpfile"
    continue
  fi

  {
    echo
    if [[ -f "$solfile" ]]; then
      echo "===== SOLUTION (from $solfile) ====="
      cat "$solfile"
      rm -f "$solfile"
    else
      echo "===== SOLUTION ====="
      echo "No .sol file was written by SCIP."
    fi
  } >> "$outfile"

  echo "Done: $outfile"
done