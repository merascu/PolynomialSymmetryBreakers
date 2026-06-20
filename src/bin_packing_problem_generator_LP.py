"""bin-packing-problem-generator.py

Bin Packing (Optimization) -> LP (.lp)

Run (all args are mandatory):
  python bin-packing-problem-generator.py --B=100 --n=2000 --classes=5 --seed=2042
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from typing import List


def write_binpacking_lp(sizes: List[int], B: int, filepath: str) -> None:
    n = len(sizes)
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    def y(j: int) -> str:
        return f"y_{j}"

    def x(i: int, j: int) -> str:
        return f"x_{i}_{j}"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\\ Bin Packing MILP (LP format)\n")
        f.write(f"\\ B={B}, n={n}, sizes={sizes}\n\n")

        f.write("Minimize\n")
        f.write(" obj: " + " + ".join(y(j) for j in range(n)) + "\n\n")

        f.write("Subject To\n")

        for i in range(n):
            f.write(f" assign_{i}: " + " + ".join(x(i, j) for j in range(n)) + " = 1\n")

        for j in range(n):
            lhs = " + ".join(f"{sizes[i]} {x(i, j)}" for i in range(n)) or "0"
            f.write(f" cap_{j}: {lhs} - {B} {y(j)} <= 0\n")

        f.write("\nBinary\n")
        for j in range(n):
            f.write(f" {y(j)}\n")
        for i in range(n):
            for j in range(n):
                f.write(f" {x(i, j)}\n")
        f.write("End\n")


def hard_half_capacity_classes_instance(n: int, B: int, classes: int, seed: int) -> List[int]:
    if n <= 0:
        raise ValueError("--n must be positive")
    if B <= 1:
        raise ValueError("--B must be at least 2")
    if classes <= 0:
        raise ValueError("--classes must be positive")

    rng = random.Random(seed + n)
    half = B // 2

    if classes % 2 == 1:
        k = classes // 2
        values = list(range(half - k, half + k + 1))
    else:
        values = list(range(half - (classes // 2 - 1), half + classes // 2 + 1))

    values = [v for v in values if 1 <= v <= B - 1]
    return [rng.choice(values) for _ in range(n)]


def generate_instance(B: int, n: int, classes: int, seed: int) -> str:
    out_dir = "bin_pack_prob"
    os.makedirs(out_dir, exist_ok=True)

    sizes = hard_half_capacity_classes_instance(n=n, B=B, classes=classes, seed=seed)
    sizes.sort()

    filename = f"hardness_halfcap_sorted_n{n}_B{B}_classes{classes}_seed{seed+n}.lp"
    path = os.path.join(out_dir, filename)

    write_binpacking_lp(sizes, B, path)
    return path


def main() -> None:
    import sys

    parser = argparse.ArgumentParser(
        description="Generate bin packing MILP instances in LP format.",
        usage="python %(prog)s --B=100 --n=1000 --classes=9 --seed=15",
        allow_abbrev=False,
    )

    parser.add_argument("--B", type=int, help="Bin capacity (mandatory, must be given as --B=...)")
    parser.add_argument("--n", type=int, help="Number of items (mandatory, must be given as --n=...)")
    parser.add_argument("--classes", type=int, help="Number of size classes (mandatory, must be given as --classes=...)")
    parser.add_argument("--seed", type=int, help="Base RNG seed (mandatory, must be given as --seed=...)")

    # Enforce --x=y (reject --x y)
    forbidden_space_flags = {"--B", "--n", "--classes", "--seed"}
    for tok in sys.argv[1:]:
        if tok in forbidden_space_flags:
            parser.error(f"Use '{tok}=<int>' (with '=') rather than '{tok} <int>'.")

    args = parser.parse_args()

    # Enforce presence of all mandatory flags (without required=True)
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