#!/usr/bin/env python3
"""
gen_files_with_sb_nonlinear.py

Takes:
  1) a base LP file (in CPLEX/LP format)
  2) a directory containing many files, each holding some LP constraints (these are the nonlinear symmetry breakers)

Outputs:
  a directory with LP files obtained by iaugumenting the initial LP problem with the non-linear symmetry breakers

Usage:
  python gen_files_with_sb_nonlinear base.lp nonlin_sb_dir lp_out_dir

"""
import argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_lp")
    ap.add_argument("constraints_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--pattern", default="*")
    args = ap.parse_args()

    base_path = Path(args.base_lp)
    cons_dir = Path(args.constraints_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_lines = base_path.read_text(encoding="utf-8").splitlines(keepends=True)

    # Find where "Binary" starts (insert constraints right before it)
    try:
        insert_at = next(i for i, ln in enumerate(base_lines) if ln.strip().lower() == "binary")
    except StopIteration:
        raise SystemExit("Error: base LP has no 'Binary' section header.")

    for snip in sorted(p for p in cons_dir.glob(args.pattern) if p.is_file()):
        lines = snip.read_text(encoding="utf-8").splitlines()

        # Drop optional "Subject To" header; keep non-empty, non-comment lines
        if lines and lines[0].strip().lower() == "subject to":
            lines = lines[1:]
        constraints = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("\\")]

        block = [c.rstrip("\n") + "\n" for c in constraints]
        block += ["\n"]

        merged = base_lines[:]
        merged[insert_at:insert_at] = block

        out_file = out_dir / f"{snip.stem}_nonlin.lp"
        out_file.write_text("".join(merged), encoding="utf-8")
        print("Wrote:", out_file)

if __name__ == "__main__":
    main()
