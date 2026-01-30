#!/usr/bin/env python3
"""gen_files_with_sb.py

Run:
  python gen_files_with_sb.py base_lp_file="filename.lp" sbs_dir="dir_path" gen_lp_files="dir_path"

This script:
- reads a base LP file (CPLEX/LP format)
- reads every snippet file from sbs_dir (each containing LP constraints)
- inserts each snippet right before the "Binary" section in the base LP
- writes one augmented LP file per snippet into gen_lp_files

Notes:
- All three arguments are mandatory.
- Arguments must be given as key="value" (with '=') and may appear in any order.
- Output directory is created if it does not exist.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict


REQUIRED_KEYS = ("base_lp_file", "sbs_dir", "gen_lp_files")


def _usage(prog: str) -> str:
    return f'python {prog} base_lp_file="filename.lp" sbs_dir="dir_path" gen_lp_files="dir_path"'


def _parse_kv_args(argv: list[str]) -> Dict[str, str]:
    """
    Parse args of the form key="value" (or key=value).
    Enforces:
      - only key=value tokens (no positional args)
      - required keys present
      - values may contain spaces if quoted by the shell
    """
    prog = os.path.basename(argv[0])
    args = argv[1:]

    if len(args) == 1 and args[0] in ("-h", "--help"):
        print(_usage(prog))
        sys.exit(0)

    kv: Dict[str, str] = {}
    for tok in args:
        if "=" not in tok:
            raise SystemExit(f"Error: expected key=value, got '{tok}'.\nUsage: {_usage(prog)}")
        key, value = tok.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not key:
            raise SystemExit(f"Error: empty key in '{tok}'.\nUsage: {_usage(prog)}")
        if key in kv:
            raise SystemExit(f"Error: duplicate argument '{key}'.\nUsage: {_usage(prog)}")

        kv[key] = value

    missing = [k for k in REQUIRED_KEYS if k not in kv or kv[k] == ""]
    if missing:
        missing_str = ", ".join(missing)
        raise SystemExit(f"Error: missing mandatory arguments: {missing_str}.\nUsage: {_usage(prog)}")

    unknown = [k for k in kv.keys() if k not in REQUIRED_KEYS]
    if unknown:
        raise SystemExit(
            f"Error: unknown argument(s): {', '.join(unknown)}.\n"
            f"Allowed: {', '.join(REQUIRED_KEYS)}\n"
            f"Usage: {_usage(prog)}"
        )

    return kv


def main() -> None:
    prog = os.path.basename(sys.argv[0])
    kv = _parse_kv_args(sys.argv)

    base_path = Path(kv["base_lp_file"])
    cons_dir = Path(kv["sbs_dir"])
    out_dir = Path(kv["gen_lp_files"])
    out_dir.mkdir(parents=True, exist_ok=True)

    if not base_path.is_file():
        raise SystemExit(f"Error: base LP file not found: {base_path}")
    if not cons_dir.is_dir():
        raise SystemExit(f"Error: sbs_dir is not a directory: {cons_dir}")

    base_lines = base_path.read_text(encoding="utf-8").splitlines(keepends=True)

    try:
        insert_at = next(i for i, ln in enumerate(base_lines) if ln.strip().lower() == "binary")
    except StopIteration:
        raise SystemExit("Error: base LP has no 'Binary' section header.")

    snippet_files = sorted(p for p in cons_dir.glob("*") if p.is_file())
    if not snippet_files:
        raise SystemExit(f"Error: no constraint files found in: {cons_dir}")

    for snip in snippet_files:
        lines = snip.read_text(encoding="utf-8").splitlines()

        if lines and lines[0].strip().lower() == "subject to":
            lines = lines[1:]

        constraints = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("\\")]

        block = [c.rstrip("\n") + "\n" for c in constraints]
        block += ["\n"]

        merged = base_lines[:]
        merged[insert_at:insert_at] = block

        out_file = out_dir / f"{snip.stem}.lp"
        out_file.write_text("".join(merged), encoding="utf-8")
        print("Wrote:", out_file)

    # Optional: final reminder of exact usage requested
    # print("Done. Usage was:", _usage(prog))


if __name__ == "__main__":
    main()