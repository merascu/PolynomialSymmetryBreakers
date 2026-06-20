#!/usr/bin/env bash

set -euo pipefail

DIR="${1:-.}"
TIMEOUT="10m"

for file in "$DIR"/*.smt2; do
    [ -e "$file" ] || continue

    base="${file%.smt2}"
    out="${base}.out"

    echo "Running with timeout $TIMEOUT: z3 -st \"$file\" > \"$out\""

    if timeout "$TIMEOUT" z3 -st "$file" > "$out"; then
        echo "Finished: $file"
    else
        status=$?
        if [ "$status" -eq 124 ]; then
            echo "Timed out after $TIMEOUT: $file"
            echo "TIMEOUT after $TIMEOUT" >> "$out"
        else
            echo "Failed with exit code $status: $file"
            echo "FAILED with exit code $status" >> "$out"
        fi
    fi
done