"""bin-packing-problem-generator.py

Bin Packing (Optimization) -> LP (.lp)

This program:
- generates bin-packing instances where B capacity is the capacity of each bin, we have n items,
  each item having roughly 1/2 of the capacity of the bin.
- it writes each instance as a linear programming problem in LP format.

LP model
  minimize  sum_j y_j
  subject to
    (Assign)  sum_j x_{i,j} = 1                      for all items i
    (Cap)     sum_i sizes[i] * x_{i,j} - B*y_j <= 0  for all bins j
    x_{i,j}, y_j are binary

Notes
- We use n potential bins for an instance with n items (standard upper bound).
- Output files are .lp.

Run:
  python bin-packing-problem-generator.py --out_dir lp_out
"""

from __future__ import annotations

import argparse
import os
import random
from typing import List


def write_binpacking_lp(sizes: List[int], B: int, filepath: str) -> None:
    """Write the bin packing MILP in CPLEX LP format."""
    n = len(sizes)
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    def y(j: int) -> str:
        return f"y_{j}"

    def x(i: int, j: int) -> str:
        return f"x_{i}_{j}"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\\ Bin Packing MILP (LP format)\n")
        f.write(f"\\ B={B}, n={n}, sizes={sizes}\n\n")

        # Objective
        f.write("Minimize\n")
        f.write(" obj: ")
        f.write(" + ".join([y(j) for j in range(n)]))
        f.write("\n\n")

        f.write("Subject To\n")

        # Assignment constraints: each item in exactly one bin
        for i in range(n):
            f.write(f" assign_{i}: ")
            f.write(" + ".join([x(i, j) for j in range(n)]))
            f.write(" = 1\n")

        # Capacity constraints
        for j in range(n):
            f.write(f" cap_{j}: ")
            lhs_terms = [f"{sizes[i]} {x(i, j)}" for i in range(n)]
            lhs = " + ".join(lhs_terms) if lhs_terms else "0"
            f.write(f"{lhs} - {B} {y(j)} <= 0\n")

        f.write("\nBinary\n")

        # Declare binaries
        for j in range(n):
            f.write(f" {y(j)}\n")
        for i in range(n):
            for j in range(n):
                f.write(f" {x(i, j)}\n")

        f.write("End\n")

def hard_half_capacity_classes_instance(n: int, B: int, classes: int, seed: int = 0) -> List[int]:
    """
    Generate n item sizes taking `classes` consecutive values centered at B/2.
    Examples for B=100:
      classes=3 -> {49, 50, 51}
      classes=4 -> {49, 50, 51, 52}
      classes=5 -> {48, 49, 50, 51, 52}
    """
    if n <= 0:
        raise ValueError("--n must be positive")
    if B <= 1:
        raise ValueError("--B must be at least 2")
    if classes <= 0:
        raise ValueError("--classes must be positive")

    rng = random.Random(seed + n)
    half = B // 2

    # Determine allowed size values
    if classes % 2 == 1:
        # Odd: perfectly symmetric
        k = classes // 2
        values = list(range(half - k, half + k + 1))
    else:
        # Even: slightly skewed upward (deterministic choice)
        values = list(range(half - (classes // 2 - 1), half + classes // 2 + 1))

    # Safety clamp (should not matter for reasonable B)
    values = [v for v in values if 1 <= v <= B - 1]

    # Sample sizes uniformly from allowed values
    sizes = [rng.choice(values) for _ in range(n)]
    return sizes

def generate_hardness_instances(B: int, n: int, classes: int, out_dir: str, seed: int) -> None:
    os.makedirs(out_dir, exist_ok=True)

    sizes = hard_half_capacity_classes_instance(n=n, B=B, classes=classes, seed=seed)
    sizes.sort()  # increasing order (as requested / consistent with your earlier behavior)

    path = os.path.join(
        out_dir,
        f"hardness_halfcap_sorted_n{n}_B{B}_classes{classes}_seed{seed+n}.lp"
    )
    write_binpacking_lp(sizes, B, path)
    print(f"Wrote: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bin packing MILP instances in LP format.")
    parser.add_argument("--out_dir", default="lp_out", help="Output directory for .lp files")
    parser.add_argument("--seed", type=int, default=42, help="Base RNG seed (default: 42)")
    parser.add_argument("--B", type=int, default=100, help="Bin capacity (default: 100)")
    parser.add_argument("--n", type=int, default=200, help="Number of items (default: 200)")
    parser.add_argument("--classes", type=int, default=3, help="Number of classes for item weights (default: 3)")

    args = parser.parse_args()

    # ✅ Now uses ALL 5 arguments from main()
    generate_hardness_instances(
        B=args.B,
        n=args.n,
        classes=args.classes,
        out_dir=args.out_dir,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
