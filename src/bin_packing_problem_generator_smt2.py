"""bin-packing-problem-generator-smt2.py

Bin Packing (Optimization) -> SMT-LIB v2 (.smt2)

Run:
  python bin-packing-problem-generator-smt2.py --B=100 --n=2000 --classes=5 --seed=2042

The generated SMT-LIB file uses QF_LIA integer variables constrained to 0/1 and
an optimization objective compatible with Optimize-capable SMT solvers such as Z3.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from typing import List


def write_binpacking_smt2(sizes: List[int], B: int, filepath: str) -> None:
    """Write a bin-packing optimization instance in SMT-LIB v2 format.

    Variables:
      y_j     = 1 iff bin j is used, otherwise 0
      x_i_j   = 1 iff item i is assigned to bin j, otherwise 0

    Objective:
      minimize sum_j y_j
    """
    n = len(sizes)
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    def y(j: int) -> str:
        return f"y_{j}"

    def x(i: int, j: int) -> str:
        return f"x_{i}_{j}"

    def sum_terms(terms: List[str]) -> str:
        if not terms:
            return "0"
        if len(terms) == 1:
            return terms[0]
        return "(+ " + " ".join(terms) + ")"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("; Bin Packing Optimization (SMT-LIB v2 format)\n")
        f.write(f"; B={B}, n={n}, sizes={sizes}\n")
        f.write("; Uses Int variables constrained to 0/1 and an Optimize objective.\n\n")

        f.write("(set-logic QF_LIA)\n")
        f.write("(set-option :tactic.default_tactic smt)\n")
        f.write("(set-option :produce-models true)\n\n")

        # Declare bin-use variables.
        for j in range(n):
            f.write(f"(declare-const {y(j)} Int)\n")

        # Declare item-assignment variables.
        for i in range(n):
            for j in range(n):
                f.write(f"(declare-const {x(i, j)} Int)\n")
        f.write("\n")

        # Binary domains: each variable is either 0 or 1.
        f.write("; Binary domains\n")
        for j in range(n):
            f.write(f"(assert (or (= {y(j)} 0) (= {y(j)} 1)))\n")
        for i in range(n):
            for j in range(n):
                f.write(f"(assert (or (= {x(i, j)} 0) (= {x(i, j)} 1)))\n")
        f.write("\n")

        # Each item must be assigned to exactly one bin.
        f.write("; Assignment constraints: each item goes to exactly one bin\n")
        for i in range(n):
            row = sum_terms([x(i, j) for j in range(n)])
            f.write(f"(assert (= {row} 1))\n")
        f.write("\n")

        # Bin capacities: sum_i size_i * x_i_j <= B * y_j.
        f.write("; Capacity constraints\n")
        for j in range(n):
            weighted_terms = [f"(* {sizes[i]} {x(i, j)})" for i in range(n)]
            lhs = sum_terms(weighted_terms)
            f.write(f"(assert (<= {lhs} (* {B} {y(j)})))\n")
        f.write("\n")

        objective = sum_terms([y(j) for j in range(n)])
        f.write("; Minimize the number of used bins\n")
        f.write(f"(minimize {objective})\n")
        f.write("(check-sat)\n")
        f.write("(get-objectives)\n")
        f.write("(get-model)\n")


def hard_half_capacity_classes_instance(n: int, B: int, classes: int, seed: int) -> List[int]:
    if n <= 0:
        raise ValueError("--n must be positive")
    if B <= 1:
        raise ValueError("--B must be at least 2")
    if classes <= 0:
        raise ValueError("--classes must be positive")

    rng = random.Random(seed)
    half = B // 2

    if classes % 2 == 1:
        k = classes // 2
        values = list(range(half - k, half + k + 1))
    else:
        values = list(range(half - (classes // 2 - 1), half + classes // 2 + 1))

    values = [v for v in values if 1 <= v <= B - 1]
    if not values:
        raise ValueError("No valid item sizes generated; check --B and --classes")

    return [rng.choice(values) for _ in range(n)]


def generate_instance(B: int, n: int, classes: int, seed: int) -> str:
    sizes = hard_half_capacity_classes_instance(n=n, B=B, classes=classes, seed=seed)
    sizes.sort()

    filename = f"hardness_halfcap_sorted_n{n}_B{B}_classes{classes}_seed{seed}.smt2"

    write_binpacking_smt2(sizes, B, filename)
    return filename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate bin packing optimization instances in SMT-LIB v2 format.",
        usage="python %(prog)s --B=100 --n=1000 --classes=9 --seed=15",
        allow_abbrev=False,
    )

    parser.add_argument("--B", type=int, help="Bin capacity (mandatory, must be given as --B=...)")
    parser.add_argument("--n", type=int, help="Number of items (mandatory, must be given as --n=...)")
    parser.add_argument("--classes", type=int, help="Number of size classes (mandatory, must be given as --classes=...)")
    parser.add_argument("--seed", type=int, help="Base RNG seed (mandatory, must be given as --seed=...)")

    # Enforce --x=y (reject --x y), matching the LP generator's interface.
    forbidden_space_flags = {"--B", "--n", "--classes", "--seed"}
    for tok in sys.argv[1:]:
        if tok in forbidden_space_flags:
            parser.error(f"Use '{tok}=<int>' (with '=') rather than '{tok} <int>'.")

    args = parser.parse_args()

    # Enforce presence of all mandatory flags without required=True.
    missing_flags = []
    if args.B is None:
        missing_flags.append("--B")
    if args.n is None:
        missing_flags.append("--n")
    if args.classes is None:
        missing_flags.append("--classes")
    if args.seed is None:
        missing_flags.append("--seed")

    if missing_flags:
        parser.error("Missing mandatory arguments: " + ", ".join(missing_flags) + ". Use the form --x=<int>.")

    path = generate_instance(B=args.B, n=args.n, classes=args.classes, seed=args.seed)
    print(f"Wrote: {path}")


if __name__ == "__main__":
    main()
