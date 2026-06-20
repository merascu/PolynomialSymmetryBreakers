#!/usr/bin/env python3
"""
Combine each LP file with every pair of:
  - *_constraints.lp
  - *_new_variables.lp
Usage:
    python expand_lp_files.py <lp_input_dir> <pairs_dir> <output_dir>

Inputs:
    1. lp_input_dir : directory containing .lp files
    2. pairs_dir    : directory containing many matching pairs:
                        <name>_constraints.lp
                        <name>_new_variables.lp
    3. output_dir   : directory where generated .lp files are written

Output:
    For every LP file and for every valid pair of files, generate one new LP file
    in output_dir with:
      - the new variables added to the Binary section
      - the new constraints added before the Binary/End section

Assumptions about LP files:
    - They contain an "End" line.
    - They may contain a "Binary" section.
    - If no Binary section exists, one is created before "End".
    - Constraints are inserted before the Binary section if it exists,
      otherwise before End.

Example pair names:
    sample_constraints.lp
    sample_new_variables.lp
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple


def read_nonempty_lines(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def find_pairs(pairs_dir: Path) -> List[Tuple[str, Path, Path]]:
    """
    Find matching pairs:
        <base>_constraints.lp
        <base>_new_variables.lp
    """
    constraints_map: Dict[str, Path] = {}
    variables_map: Dict[str, Path] = {}

    for p in pairs_dir.iterdir():
        if not p.is_file():
            continue

        name = p.name
        if name.endswith("_constraints.lp"):
            base = name[: -len("_constraints.lp")]
            constraints_map[base] = p
        elif name.endswith("_new_variables.lp"):
            base = name[: -len("_new_variables.lp")]
            variables_map[base] = p

    common_bases = sorted(set(constraints_map) & set(variables_map))
    return [(base, constraints_map[base], variables_map[base]) for base in common_bases]


def find_section_index(lines: List[str], section_name: str) -> int:
    target = section_name.lower()
    for i, line in enumerate(lines):
        if line.strip().lower() == target:
            return i
    return -1


def find_end_index(lines: List[str]) -> int:
    idx = find_section_index(lines, "End")
    if idx == -1:
        raise ValueError("LP file does not contain an 'End' line.")
    return idx


def collect_existing_binary_variables(lines: List[str]) -> Tuple[int, int, List[str]]:
    """
    Returns:
        (binary_start_index, binary_end_index, variables)

    binary_end_index is the first line index after the binary variable block.
    If Binary section does not exist, returns (-1, -1, []).
    """
    binary_idx = find_section_index(lines, "Binary")
    if binary_idx == -1:
        return -1, -1, []

    end_idx = find_end_index(lines)

    vars_found: List[str] = []
    i = binary_idx + 1
    while i < end_idx:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        lower = stripped.lower()
        if lower in {
            "general",
            "generals",
            "binary",
            "binaries",
            "bounds",
            "semi",
            "semis",
            "sos",
            "end",
            "subject to",
            "such that",
            "st",
            "minimize",
            "maximize",
            "minimum",
            "maximum",
        }:
            break

        vars_found.extend(stripped.split())
        i += 1

    return binary_idx, i, vars_found


def merge_lp_file(lp_path: Path, constraints_path: Path, variables_path: Path, output_path: Path) -> None:
    lp_lines = lp_path.read_text(encoding="utf-8").splitlines()
    new_constraints = read_nonempty_lines(constraints_path)
    new_variables = read_nonempty_lines(variables_path)

    if not lp_lines:
        raise ValueError(f"Empty LP file: {lp_path}")

    end_idx = find_end_index(lp_lines)
    binary_idx, binary_end_idx, existing_binary_vars = collect_existing_binary_variables(lp_lines)

    # Deduplicate variables while preserving order
    existing_set = set(existing_binary_vars)
    vars_to_add = []
    for var in new_variables:
        if var not in existing_set:
            vars_to_add.append(var)
            existing_set.add(var)

    # Insert new constraints
    # If Binary exists, insert before Binary.
    # Otherwise insert before End.
    constraint_insert_idx = binary_idx if binary_idx != -1 else end_idx
    updated_lines = lp_lines[:constraint_insert_idx] + new_constraints + lp_lines[constraint_insert_idx:]

    # After constraint insertion, indices may shift
    if binary_idx != -1:
        binary_idx = find_section_index(updated_lines, "Binary")
        binary_end_idx, _, _ = binary_idx, binary_end_idx, existing_binary_vars

    # Insert / extend Binary section
    if binary_idx != -1:
        # Recompute binary block end after constraint insertion
        binary_idx, binary_end_idx, _ = collect_existing_binary_variables(updated_lines)
        updated_lines = (
            updated_lines[:binary_end_idx]
            + vars_to_add
            + updated_lines[binary_end_idx:]
        )
    else:
        end_idx = find_end_index(updated_lines)
        binary_block = []
        if vars_to_add:
            binary_block.append("Binary")
            binary_block.extend(vars_to_add)
        updated_lines = updated_lines[:end_idx] + binary_block + updated_lines[end_idx:]

    output_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="For each LP file and each constraints/variables pair, generate an augmented LP file."
    )
    parser.add_argument("lp_input_dir", help="Directory containing input .lp files")
    parser.add_argument("pairs_dir", help="Directory containing *_constraints.lp and *_new_variables.lp pairs")
    parser.add_argument("output_dir", help="Directory where generated .lp files will be saved")
    args = parser.parse_args()

    lp_input_dir = Path(args.lp_input_dir)
    pairs_dir = Path(args.pairs_dir)
    output_dir = Path(args.output_dir)

    if not lp_input_dir.is_dir():
        raise SystemExit(f"Not a directory: {lp_input_dir}")
    if not pairs_dir.is_dir():
        raise SystemExit(f"Not a directory: {pairs_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    lp_files = sorted(lp_input_dir.glob("*.lp"))
    if not lp_files:
        raise SystemExit(f"No .lp files found in: {lp_input_dir}")

    pairs = find_pairs(pairs_dir)
    if not pairs:
        raise SystemExit(
            f"No matching pairs found in {pairs_dir}. Expected files like "
            f"'*_constraints.lp' and '*_new_variables.lp'."
        )

    for lp_file in lp_files:
        lp_base = lp_file.stem

        for pair_base, constraints_file, variables_file in pairs:
            print("lp_base ", lp_base)
            print("pair_base ", pair_base)
            output_name = f"{lp_base}__{pair_base}.lp"
            output_path = output_dir / output_name
            merge_lp_file(lp_file, constraints_file, variables_file, output_path)

    print(f"Generated {len(lp_files) * len(pairs)} file(s) in {output_dir}")


if __name__ == "__main__":
    main()