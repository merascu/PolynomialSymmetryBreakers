#!/usr/bin/env python3
"""Generate bin-packing optimization instances in LP or SMT-LIB2 format.
classes = 3 or 5 or 7 or 9
outtype = lp or smt2

Example:
    python bin-packing-problem-generator.py \
        --B=100 --n=2000 --classes=5 --seed=2042 --outtype=lp

    python bin-packing-problem-generator.py \
        --B=200 --n=1000 --classes=9 --seed=2042 --outtype=smt2


"""

import argparse
import random
from pathlib import Path
from typing import Iterable, TextIO


def item_sizes(n: int, capacity: int, classes: int, seed: int) -> list[int]:
    """Return sorted item sizes clustered around half the bin capacity."""
    half = capacity // 2
    left = (classes - 1) // 2
    # values saves the possible item-size classes around half the bin capacity.
    values = list(range(half - left, half + classes - left))

    print("half ", half, "left ", left, "values ", values)

    rng = random.Random(seed)
    return sorted(rng.choice(values) for _ in range(n))


def x(i: int, j: int) -> str:
    return f"x_{i}_{j}"


def y(j: int) -> str:
    return f"y_{j}"


def write_lp(out: TextIO, sizes: list[int], capacity: int) -> None:
    """Write a MILP model in CPLEX LP format."""
    n = len(sizes)
    out.write(f"\\ Bin Packing MILP; B={capacity}, n={n}, sizes={sizes}\n\n")
    out.write("Minimize\n obj: " + " + ".join(y(j) for j in range(n)) + "\n\n")
    out.write("Subject To\n")

    for i in range(n):
        out.write(f" assign_{i}: " + " + ".join(x(i, j) for j in range(n)) + " = 1\n")
    for j in range(n):
        terms = " + ".join(f"{size} {x(i, j)}" for i, size in enumerate(sizes))
        out.write(f" cap_{j}: {terms} - {capacity} {y(j)} <= 0\n")

    out.write("\nBinary\n")
    out.writelines(f" {y(j)}\n" for j in range(n))
    out.writelines(f" {x(i, j)}\n" for i in range(n) for j in range(n))
    out.write("End\n")


def smt_sum(terms: Iterable[str]) -> str:
    terms = list(terms)
    if not terms:
        return "0"
    return terms[0] if len(terms) == 1 else f"(+ {' '.join(terms)})"


def write_smt2(out: TextIO, sizes: list[int], capacity: int) -> None:
    """Write an optimization model in SMT-LIB2 using integer 0/1 variables."""
    n = len(sizes)
    out.write(f"; Bin Packing Optimization; B={capacity}, n={n}, sizes={sizes}\n\n")
    #out.write("(set-logic QF_LIA)\n(set-option :produce-models true)\n\n")

    out.writelines(f"(declare-const {y(j)} Int)\n" for j in range(n))
    out.writelines(f"(declare-const {x(i, j)} Int)\n" for i in range(n) for j in range(n))
    out.write("\n")

    out.writelines(f"(assert (or (= {y(j)} 0) (= {y(j)} 1)))\n" for j in range(n))
    out.writelines(
        f"(assert (or (= {x(i, j)} 0) (= {x(i, j)} 1)))\n"
        for i in range(n)
        for j in range(n)
    )
    out.write("\n")

    for i in range(n):
        out.write(f"(assert (= {smt_sum(x(i, j) for j in range(n))} 1))\n")
    for j in range(n):
        load = smt_sum(f"(* {size} {x(i, j)})" for i, size in enumerate(sizes))
        out.write(f"(assert (<= {load} (* {capacity} {y(j)})))\n")

    out.write(f"\n(minimize {smt_sum(y(j) for j in range(n))})\n")
    out.write("(check-sat)\n(get-objectives)\n(get-model)\n")


WRITERS = {"lp": write_lp, "smt2": write_smt2}


def positive(name: str):
    def parse(value: str) -> int:
        number = int(value)
        if number < 1:
            raise argparse.ArgumentTypeError(f"{name} must be positive")
        return number

    return parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a bin-packing optimization instance in LP or SMT-LIB v2 format.",
        allow_abbrev=False,
    )
    parser.add_argument("--B", type=positive("--B"), required=True, help="bin capacity")
    parser.add_argument("--n", type=positive("--n"), required=True, help="number of items")
    parser.add_argument("--classes", type=positive("--classes"), required=True, help="number of size classes")
    parser.add_argument("--seed", type=int, required=True, help="random seed")
    parser.add_argument(
        "--outtype",
        type=str.lower,
        choices=WRITERS,
        required=True,
        help="output format: lp or smt2",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sizes = item_sizes(args.n, args.B, args.classes, args.seed)

    output = Path(
        f"hardness_halfcap_sorted_n{args.n}_B{args.B}_classes{args.classes}_seed{args.seed}.{args.outtype}"
    )

    with output.open("w", encoding="utf-8", newline="\n") as file:
        WRITERS[args.outtype](file, sizes, args.B)

    print(f"Wrote: {output}")


if __name__ == "__main__":
    main()