#!/usr/bin/env python3
"""Generate LP, SMT-LIB2, or OMT models augmented with symmetry breakers.

Run as:

    python gen_files_with_sbs.py \
        --base_file="base.lp" \
        --sbs_dir="sbs/" \
        --prob_with_sbs="prob_with_sbs/" \
        --sbs_type="linear" \
        --base_file_type="lp"

    python gen_files_with_sbs.py \
        --base_file="base.smt2" \
        --sbs_dir="sbs/" \
        --prob_with_sbs="prob_with_sbs/" \
        --sbs_type="linear" \
        --base_file_type="smt2"

    python gen_files_with_sbs.py \
        --base_file="base.smt2" \
        --sbs_dir="sbs/" \
        --prob_with_sbs="prob_with_sbs/" \
        --sbs_type="linear" \
        --base_file_type="omt"
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


CANONICAL_KEYS = {
    "base_file",
    "sbs_dir",
    "prob_with_sbs",
    "sbs_type",
    "base_file_type",
}
LP_SECTION_HEADERS = {
    "bounds",
    "bound",
    "binary",
    "binaries",
    "general",
    "generals",
    "integer",
    "integers",
    "semi",
    "semis",
    "sos",
    "end",
}
LP_CONSTRAINT_HEADERS = {"subject to", "such that", "st", "s.t."}
SMT2_TERMINAL_PREFIXES = (
    "(check-sat",
    "(check-sat-assuming",
    "(get-model",
    "(get-value",
    "(get-assignment",
    "(get-objectives",
    "(exit",
)
# SMT2_TARGET_OBJECTIVE = (
#     "(minimize (+ y_0 y_1 y_2 y_3 y_4 y_5 y_6 y_7 y_8 y_9))"
# )
SMT2_GET_OBJECTIVES = "(get-objectives)"


def usage(prog: str) -> str:
    return (
        f'python {prog} --base_file="filename" --sbs_dir="dir_path" '
        '--prob_with_sbs="dir_path" --sbs_type="linear|quadratic" '
        '--base_file_type="lp|smt2|omt"'
    )

MINIMIZE_Y_OBJECTIVE_RE = re.compile(
    r"^\(minimize\s+\(\+\s+y_\d+(?:\s+y_\d+)*\)\)$",
    re.IGNORECASE,
)

def normalize_smt2_line(line: str) -> str:
    """Normalize whitespace and case for matching complete SMT-LIB commands."""
    return re.sub(r"\s+", " ", line.strip()).lower()


def find_target_objective(lines: Sequence[str]) -> int:
    matches = [
        index
        for index, line in enumerate(lines)
        if normalize_smt2_line(line).startswith("(minimize ")
    ]

    if not matches:
        raise ValueError(
            "The base model does not contain a minimize objective."
        )

    if len(matches) > 1:
        raise ValueError(
            "The base model contains more than one minimize objective."
        )

    return matches[0]

def parse_kv_args(argv: Sequence[str]) -> Dict[str, str]:
    """Parse and validate --key=value arguments."""
    prog = os.path.basename(argv[0])
    tokens = list(argv[1:])

    if len(tokens) == 1 and tokens[0] in {"-h", "--help"}:
        print(__doc__.rstrip())
        print("\nUsage:\n  " + usage(prog))
        raise SystemExit(0)

    parsed: Dict[str, str] = {}
    for token in tokens:
        if not token.startswith("--"):
            raise SystemExit(
                f"Error: every argument must start with '--'; got {token!r}.\n"
                f"Usage: {usage(prog)}"
            )
        if "=" not in token:
            raise SystemExit(
                f"Error: expected --key=value, got {token!r}.\nUsage: {usage(prog)}"
            )
        raw_key, raw_value = token[2:].split("=", 1)
        key = raw_key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if not key:
            raise SystemExit(f"Error: empty argument name.\nUsage: {usage(prog)}")
        if key not in CANONICAL_KEYS:
            allowed = [f"--{name}" for name in sorted(CANONICAL_KEYS)]
            raise SystemExit(
                f"Error: unknown argument '--{raw_key}'. Allowed: {', '.join(allowed)}"
            )
        if key in parsed:
            raise SystemExit(f"Error: duplicate argument for {key!r}.")
        parsed[key] = value

    required = (
        "base_file",
        "sbs_dir",
        "prob_with_sbs",
        "sbs_type",
        "base_file_type",
    )
    missing = [key for key in required if not parsed.get(key)]
    if missing:
        raise SystemExit(
            f"Error: missing mandatory argument(s): {', '.join(missing)}.\n"
            f"Usage: {usage(prog)}"
        )

    sbs_type = parsed["sbs_type"].strip().lower()
    if sbs_type == "linear":
        parsed["sbs_type"] = "linear"
    elif sbs_type == "quadratic":
        parsed["sbs_type"] = "quadratic"
    else:
        raise SystemExit("Error: sbs_type must be 'linear', or 'quadratic'.")

    file_type = parsed["base_file_type"].strip().lower().lstrip(".")
    if file_type not in {"lp", "smt2", "omt"}:
        raise SystemExit("Error: base_file_type must be 'lp', 'smt2', or 'omt'.")
    parsed["base_file_type"] = file_type

    if sbs_type == "quadratic" and file_type in {"smt2", "omt"}:
        raise SystemExit(
            "Error: quadratic symmetry breakers are not supported for SMT2/OMT "
            "files. Use sbs_type='linear' with base_file_type='smt2' or 'omt'."
        )

    return parsed


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8")


def write_lines(path: Path, lines: Sequence[str]) -> None:
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def unique_preserving_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


# ---------------------------------------------------------------------------
# LP support
# ---------------------------------------------------------------------------


def lp_header(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def find_lp_end(lines: Sequence[str]) -> int:
    for index, line in enumerate(lines):
        if lp_header(line) == "end":
            return index
    raise ValueError("LP base model does not contain an 'End' line.")


def find_lp_constraint_insertion(lines: Sequence[str]) -> int:
    """Return the first post-constraint section, or End as a fallback."""
    end_index = find_lp_end(lines)
    for index, line in enumerate(lines[: end_index + 1]):
        if lp_header(line) in LP_SECTION_HEADERS:
            return index
    return end_index


def find_lp_binary_section(lines: Sequence[str]) -> Tuple[int, int]:
    """Return [start, end) of the Binary/Binaries variable section."""
    end_index = find_lp_end(lines)
    binary_index = -1
    for index, line in enumerate(lines[:end_index]):
        if lp_header(line) in {"binary", "binaries"}:
            binary_index = index
            break
    if binary_index == -1:
        return -1, -1

    section_end = end_index
    for index in range(binary_index + 1, end_index):
        if lp_header(lines[index]) in LP_SECTION_HEADERS:
            section_end = index
            break
    return binary_index, section_end


def clean_lp_constraints(text: str) -> List[str]:
    result: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        normalized = lp_header(raw_line)
        if not stripped or stripped.startswith("\\"):
            continue
        if normalized in LP_CONSTRAINT_HEADERS or normalized == "end":
            continue
        if normalized in {"binary", "binaries"}:
            continue
        result.append(raw_line.rstrip())
    return result


def clean_lp_variables(text: str) -> List[str]:
    variables: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        normalized = lp_header(raw_line)
        if not stripped or stripped.startswith("\\"):
            continue
        if normalized in LP_SECTION_HEADERS or normalized in LP_CONSTRAINT_HEADERS:
            continue
        variables.extend(stripped.split())
    return unique_preserving_order(variables)


def existing_lp_binary_variables(lines: Sequence[str]) -> List[str]:
    binary_start, binary_end = find_lp_binary_section(lines)
    if binary_start == -1:
        return []
    variables: List[str] = []
    for line in lines[binary_start + 1 : binary_end]:
        variables.extend(line.strip().split())
    return variables


def merge_lp(
    base_text: str,
    constraints_text: str,
    variables_text: str | None = None,
) -> str:
    lines = base_text.splitlines()
    if not lines:
        raise ValueError("The LP base model is empty.")

    constraints = clean_lp_constraints(constraints_text)
    variables = clean_lp_variables(variables_text or "")

    insertion = find_lp_constraint_insertion(lines)
    constraint_block = constraints + ([""] if constraints else [])
    merged = list(lines[:insertion]) + constraint_block + list(lines[insertion:])

    if variables:
        existing = set(existing_lp_binary_variables(merged))
        variables_to_add = [name for name in variables if name not in existing]
        if variables_to_add:
            binary_start, binary_end = find_lp_binary_section(merged)
            if binary_start != -1:
                merged[binary_end:binary_end] = variables_to_add
            else:
                end_index = find_lp_end(merged)
                merged[end_index:end_index] = ["Binary", *variables_to_add]

    return "\n".join(merged).rstrip() + "\n"


# ---------------------------------------------------------------------------
# SMT-LIB2 support
# ---------------------------------------------------------------------------


def smt2_command_prefix(line: str) -> str:
    return line.lstrip().lower()


def normalize_smt2_line(line: str) -> str:
    """Normalize whitespace and case for matching complete SMT-LIB commands."""
    return re.sub(r"\s+", " ", line.strip()).lower()


def clean_smt2_block(text: str, *, declarations_only: bool = False) -> List[str]:
    result: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        prefix = stripped.lower()
        if not stripped:
            continue
        if any(prefix.startswith(command) for command in SMT2_TERMINAL_PREFIXES):
            continue
        if prefix.startswith("(set-logic"):
            continue
        if declarations_only and not stripped.startswith(";"):
            if not (
                prefix.startswith("(declare-")
                or prefix.startswith("(define-fun")
                or prefix.startswith("(define-sort")
            ):
                raise ValueError(
                    "SMT2 new-variable files must contain declarations/definitions; "
                    f"unexpected line: {stripped}"
                )
        result.append(raw_line.rstrip())
    return result


def find_smt2_declaration_insertion(lines: Sequence[str]) -> int:
    """Place declarations before constraints, objectives, or solver queries."""
    command_prefixes = (
        "(assert",
        "(assume",
        "(minimize",
        "(maximize",
        "(check-sat",
        "(get-objectives",
        "(exit",
    )
    for index, line in enumerate(lines):
        prefix = smt2_command_prefix(line)
        if prefix.startswith(command_prefixes):
            return index
    return len(lines)


def unique_smt2_declarations(
    base_lines: Sequence[str], declarations: Sequence[str]
) -> List[str]:
    existing = {normalize_smt2_line(line) for line in base_lines if line.strip()}
    result: List[str] = []
    seen = set(existing)
    for line in declarations:
        normalized = normalize_smt2_line(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(line)
    return result


def insert_smt2_declarations(
    lines: List[str], declarations: Sequence[str]
) -> None:
    declarations_to_add = unique_smt2_declarations(lines, declarations)
    if declarations_to_add:
        insertion = find_smt2_declaration_insertion(lines)
        lines[insertion:insertion] = [*declarations_to_add, ""]


def merge_smt2(
    base_text: str,
    constraints_text: str,
    variables_text: str | None = None,
) -> str:
    """Replace the target objective with SBS constraints and remove get-objectives."""
    lines = base_text.splitlines()
    if not lines:
        raise ValueError("The SMT2 base model is empty.")

    declarations = clean_smt2_block(variables_text or "", declarations_only=True)
    constraints = clean_smt2_block(constraints_text)

    objective_index = find_target_objective(lines)
    replacement = [*constraints, ""] if constraints else []
    merged = list(lines)
    merged[objective_index : objective_index + 1] = replacement
    merged = [
        line
        for line in merged
        if normalize_smt2_line(line) != normalize_smt2_line(SMT2_GET_OBJECTIVES)
    ]

    insert_smt2_declarations(merged, declarations)
    return "\n".join(merged).rstrip() + "\n"


def merge_omt(
    base_text: str,
    constraints_text: str,
    variables_text: str | None = None,
) -> str:
    """Insert SBS constraints immediately before the target objective."""
    lines = base_text.splitlines()
    if not lines:
        raise ValueError("The OMT base model is empty.")

    declarations = clean_smt2_block(variables_text or "", declarations_only=True)
    constraints = clean_smt2_block(constraints_text)

    objective_index = find_target_objective(lines)
    merged = list(lines)
    if constraints:
        merged[objective_index:objective_index] = [*constraints, ""]

    insert_smt2_declarations(merged, declarations)
    return "\n".join(merged).rstrip() + "\n"


# ---------------------------------------------------------------------------
# SBS discovery and generation
# ---------------------------------------------------------------------------


def find_linear_pairs(sbs_dir: Path, extension: str) -> List[Tuple[str, Path, Path]]:
    constraints_suffix = f"_constraints.{extension}"
    variables_suffix = f"_new_variables.{extension}"
    constraints: Dict[str, Path] = {}
    variables: Dict[str, Path] = {}

    for path in sorted(sbs_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name.endswith(constraints_suffix):
            key = path.name[: -len(constraints_suffix)]
            constraints[key] = path
        elif path.name.endswith(variables_suffix):
            key = path.name[: -len(variables_suffix)]
            variables[key] = path

    common = sorted(set(constraints) & set(variables))
    return [(key, constraints[key], variables[key]) for key in common]


def find_quadratic_snippets(sbs_dir: Path, extension: str) -> List[Path]:
    return [
        path
        for path in sorted(sbs_dir.iterdir())
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() == f".{extension}"
        and f"_constraints.{extension}" not in path.name
        and f"_new_variables.{extension}" not in path.name
    ]


def merge_model(
    base_type: str,
    base_text: str,
    constraints_text: str,
    variables_text: str | None = None,
) -> str:
    if base_type == "lp":
        return merge_lp(base_text, constraints_text, variables_text)
    if base_type == "smt2":
        return merge_smt2(base_text, constraints_text, variables_text)
    return merge_omt(base_text, constraints_text, variables_text)


def generate(
    base_file: Path,
    sbs_dir: Path,
    output_dir: Path,
    sbs_type: str,
    base_type: str,
) -> List[Path]:
    if not base_file.is_file():
        raise SystemExit(f"Error: base file not found: {base_file}")
    if not sbs_dir.is_dir():
        raise SystemExit(f"Error: sbs_dir is not a directory: {sbs_dir}")

    valid_base_suffixes = {
        "lp": {".lp"},
        "smt2": {".smt2"},
        "omt": {".smt2"},
    }[base_type]
    if base_file.suffix.lower() not in valid_base_suffixes:
        expected = " or ".join(sorted(valid_base_suffixes))
        print(
            f"Warning: base_file_type={base_type!r}, but base file suffix is "
            f"{base_file.suffix or '<none>'!r}; expected {expected}.",
            file=sys.stderr,
        )

    # Determines which type of files must be read from sbs_dir.
    # - LP uses sbs files ending in .lp.
    # - SMT2 uses sbs files ending in .smt2.
    # - OMT also uses SBS files ending in .smt2.
    sbs_extension = "lp" if base_type == "lp" else "smt2"
    output_extension = sbs_extension

    output_dir.mkdir(parents=True, exist_ok=True)
    base_text = read_text(base_file)
    generated: List[Path] = []

    if sbs_type == "linear":
        pairs = find_linear_pairs(sbs_dir, sbs_extension)
        if not pairs:
            raise SystemExit(
                f"Error: no matching linear SBS pairs found in {sbs_dir}. Expected "
                f"'<name>_constraints.{sbs_extension}' and "
                f"'<name>_new_variables.{sbs_extension}'."
            )

        for pair_name, constraints_file, variables_file in pairs:
            merged = merge_model(
                base_type,
                base_text,
                read_text(constraints_file),
                read_text(variables_file),
            )
            output_path = output_dir / f"{base_file.stem}__{pair_name}.{output_extension}"
            output_path.write_text(merged, encoding="utf-8")
            generated.append(output_path)
            print(f"Wrote: {output_path}")
    else:
        snippets = find_quadratic_snippets(sbs_dir, sbs_extension)
        if not snippets:
            raise SystemExit(f"Error: no sbs snippet files found in: {sbs_dir}")

        for snippet_file in snippets:
            merged = merge_model(base_type, base_text, read_text(snippet_file))
            output_path = output_dir / f"{snippet_file.stem}.{output_extension}"
            output_path.write_text(merged, encoding="utf-8")
            generated.append(output_path)
            print(f"Wrote: {output_path}")

    return generated


def main() -> None:
    args = parse_kv_args(sys.argv)
    generated = generate(
        base_file=Path(args["base_file"]),
        sbs_dir=Path(args["sbs_dir"]),
        output_dir=Path(args["prob_with_sbs"]),
        sbs_type=args["sbs_type"],
        base_type=args["base_file_type"],
    )
    print(f"Generated {len(generated)} file(s).")


if __name__ == "__main__":
    main()