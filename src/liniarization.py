#!/usr/bin/env python3
import argparse
import re
from collections import OrderedDict
from pathlib import Path

# Linearization method for binary variables.
# Input:
# a: … x1 * x2  … <=0
# Output:
# sb01: z_x1_x2 - x1 <= 0
# sb02: z_x1_x2 - x2 <= 0
# sb03: x1 + x2 - z_x1_x2 <= 1
#
# Run as:
# python liniarization.py --input_dir="input_dir" --output_dir="output_dir" --out_type="lp"
# python liniarization.py --input_dir="input_dir" --output_dir="output_dir" --out_type="smt2"
# All 3 arguments are mandatory
# input_dir is a directory with files which contain symetry breakers (linear and quadratic)
# in the lp format, for example: sb12: -1 x_78_12 + x_78_11 - x_73_32 + x_72_32 - x_34_90 + x_33_90 + [ -1 y_55 * y_62 - y_17 * y_62 + y_10 * y_55 + y_10 * y_17 - y_7 * y_62 + y_7 * y_10 ] <= 0


# For each input file, the script generates a pair of output files:
# (1) a file containing the linearized symmetry breakers;
# (2) a file containing the list of newly introduced variables.

LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*):\s*(.*)$")
COMPARE_RE = re.compile(r"^(.*?)([<>]?=)\s*([-+]?\d+(?:\.\d+)?)\s*$")
TERM_RE = re.compile(r"([+-]?)\s*(?:(\d+)\s+)?(.+)$")
PRODUCT_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)$"
)
SQUARE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\^\s*2$")
VARIABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NUMBER_RE = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
SPACE_RE = re.compile(r"\s+")


def clean_spaces(text):
    text = text.replace("[", " ").replace("]", " ")
    text = SPACE_RE.sub(" ", text).strip()
    text = text.replace("+ -", "- ")
    text = text.replace("- -", "+ ")
    text = text.replace("+ +", "+ ")
    return text.strip()


def split_terms(expression):
    expression = clean_spaces(expression)
    expression = expression.replace("-", "+ -")

    parts = [
        part.strip()
        for part in expression.split("+")
        if part.strip()
    ]

    terms = []

    for part in parts:
        match = TERM_RE.fullmatch(part)

        if not match:
            raise ValueError("cannot parse term: {!r}".format(part))

        sign, coefficient, body = match.groups()
        coefficient = int(coefficient) if coefficient else 1

        if sign == "-":
            coefficient *= -1

        terms.append((coefficient, clean_spaces(body)))

    return terms


def z_name(first, second):
    first, second = sorted((first, second))
    return "z_{}_{}".format(first, second)


def format_terms(terms):
    terms = [
        (coefficient, variable)
        for coefficient, variable in terms
        if coefficient != 0
    ]

    if not terms:
        return "0"

    pieces = []

    for index, item in enumerate(terms):
        coefficient, variable = item

        if coefficient == 1:
            core = variable
        elif coefficient == -1:
            core = "- {}".format(variable) if index > 0 else "-{}".format(variable)
        else:
            core = "{} {}".format(coefficient, variable)

        if index == 0:
            pieces.append(core)
        elif coefficient > 0:
            pieces.append("+ {}".format(core))
        elif coefficient == -1:
            pieces.append(core)
        else:
            pieces.append("- {} {}".format(abs(coefficient), variable))

    return clean_spaces(" ".join(pieces))


class Linearizer:
    def __init__(self):
        self.next_label = 1
        self.pair_to_z = OrderedDict()

    def new_label(self):
        label = "sb{:06d}".format(self.next_label)
        self.next_label += 1
        return label

    def linearize_term(self, coefficient, body):
        body = clean_spaces(body)

        square = SQUARE_RE.fullmatch(body)

        if square:
            return [(coefficient, square.group(1))], [], True

        product = PRODUCT_RE.fullmatch(body)

        if not product:
            return [(coefficient, body)], [], False

        first, second = product.groups()

        if first == second:
            return [(coefficient, first)], [], True

        pair = tuple(sorted((first, second)))
        variable = self.pair_to_z.get(pair)
        created = []

        if variable is None:
            variable = z_name(first, second)
            self.pair_to_z[pair] = variable
            created.append((variable, pair[0], pair[1]))

        return [(coefficient, variable)], created, True

    def auxiliary_constraints(self, variable, first, second):
        return [
            "{}: {} - {} <= 0".format(self.new_label(), variable, first),
            "{}: {} - {} <= 0".format(self.new_label(), variable, second),
            "{}: {} + {} - {} <= 1".format(
                self.new_label(), first, second, variable
            ),
        ]

    def process_constraint(self, line):
        line = line.strip()

        if not line:
            return []

        label_match = LABEL_RE.fullmatch(line)

        if label_match:
            label, body = label_match.groups()
        else:
            label = self.new_label()
            body = line

        body = clean_spaces(body)
        comparison = COMPARE_RE.fullmatch(body)

        if not comparison:
            return ["{}: {}".format(label, body)]

        left_hand_side, operator, right_hand_side = comparison.groups()
        new_terms = []
        created_pairs = []
        had_quadratic_term = False

        for coefficient, term in split_terms(left_hand_side):
            linear_terms, created, was_quadratic = self.linearize_term(
                coefficient,
                term,
            )
            new_terms.extend(linear_terms)
            created_pairs.extend(created)
            had_quadratic_term = had_quadratic_term or was_quadratic

        if had_quadratic_term:
            main_constraint = "{}: {} {} {}".format(
                label,
                format_terms(new_terms),
                operator,
                right_hand_side,
            )
        else:
            main_constraint = "{}: {}".format(label, body)

        auxiliary_constraints = []
        seen = set()

        for variable, first, second in created_pairs:
            pair = (variable, first, second)

            if pair in seen:
                continue

            seen.add(pair)
            auxiliary_constraints.extend(
                self.auxiliary_constraints(variable, first, second)
            )

        return [main_constraint] + auxiliary_constraints


def parse_linear_constraint(constraint):
    print("constraint", constraint)
    label_match = LABEL_RE.fullmatch(clean_spaces(constraint))

    if not label_match:
        raise ValueError("constraint has no valid label: {!r}".format(constraint))

    label, body = label_match.groups()
    comparison = COMPARE_RE.fullmatch(clean_spaces(body))

    if not comparison:
        raise ValueError(
            "SMT2 output requires a linear comparison: {!r}".format(constraint)
        )

    left_hand_side, operator, right_hand_side = comparison.groups()
    return label, split_terms(left_hand_side), operator, right_hand_side


def smt_number(value):
    text = str(value).strip()

    if not NUMBER_RE.fullmatch(text):
        raise ValueError("unsupported SMT2 numeric literal: {!r}".format(text))

    if text.startswith("+"):
        text = text[1:]

    if text.startswith("-"):
        return "(- {})".format(text[1:])

    return text


def smt_atom(body):
    if VARIABLE_RE.fullmatch(body):
        return body

    if NUMBER_RE.fullmatch(body):
        return smt_number(body)

    raise ValueError("unsupported SMT2 term: {!r}".format(body))


def smt_linear_expression(terms):
    pieces = []

    for coefficient, body in terms:
        if coefficient == 0:
            continue

        atom = smt_atom(body)

        if coefficient == 1:
            piece = atom
        elif coefficient == -1:
            piece = "(- {})".format(atom)
        else:
            piece = "(* {} {})".format(smt_number(coefficient), atom)

        pieces.append(piece)

    if not pieces:
        return "0"

    if len(pieces) == 1:
        return pieces[0]

    return "(+ {})".format(" ".join(pieces))


def collect_variables(constraints):
    variables = OrderedDict()
    parsed_constraints = []

    for constraint in constraints:
        parsed = parse_linear_constraint(constraint)
        parsed_constraints.append(parsed)
        terms = parsed[1]

        for coefficient, body in terms:
            del coefficient

            if VARIABLE_RE.fullmatch(body):
                variables.setdefault(body, None)
            elif not NUMBER_RE.fullmatch(body):
                raise ValueError("unsupported SMT2 term: {!r}".format(body))

    return list(variables.keys()), parsed_constraints


def write_lp_output(base_name, output_dir, constraints, new_variables):
    constraints_path = output_dir / "{}_constraints.lp".format(base_name)
    variables_path = output_dir / "{}_new_variables.lp".format(base_name)

    with constraints_path.open("w", encoding="utf-8", newline="\n") as file:
        for constraint in constraints:
            file.write(clean_spaces(constraint) + "\n")

    with variables_path.open("w", encoding="utf-8", newline="\n") as file:
        for variable in new_variables:
            file.write(variable + "\n")


def write_smt2_output(base_name, output_dir, constraints, new_variables):
    constraints_path = output_dir / "{}_constraints.smt2".format(base_name)
    variables_path = output_dir / "{}_new_variables.smt2".format(base_name)

    variables, parsed_constraints = collect_variables(constraints)

    with constraints_path.open("w", encoding="utf-8", newline="\n") as file:
        for variable in variables:
            file.write(
                "(assume (and (<= 0 {0}) (<= {0} 1)))\n".format(variable)
            )

        for parsed in parsed_constraints:
            terms = parsed[1]
            operator = parsed[2]
            right_hand_side = parsed[3]
            expression = smt_linear_expression(terms)
            file.write(
                "(assume ({} {} {}))\n".format(
                    operator,
                    expression,
                    smt_number(right_hand_side),
                )
            )

    # The companion file mirrors the LP new-variables file: it contains
    # only the variables introduced by linearization, represented using
    # SMT-LIB declarations.
    with variables_path.open("w", encoding="utf-8", newline="\n") as file:
        for variable in new_variables:
            file.write("(declare-const {} Int)\n".format(variable))


def process_file(input_path, output_dir, out_type):
    linearizer = Linearizer()
    constraints = []

    with input_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line or line.startswith("#") or line.startswith(";"):
                continue

            try:
                constraints.extend(linearizer.process_constraint(line))
            except ValueError as error:
                raise ValueError(
                    "{}:{}: {}".format(input_path, line_number, error)
                )

    base_name = input_path.stem
    new_variables = list(linearizer.pair_to_z.values())

    if out_type == "lp":
        write_lp_output(base_name, output_dir, constraints, new_variables)
    else:
        write_smt2_output(base_name, output_dir, constraints, new_variables)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Linearize products of binary variables and write LP or SMT2 output."
        ),
        allow_abbrev=False,
    )

    parser.add_argument(
        "--input_dir",
        type=Path,
        required=True,
        help="directory containing input files",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        help="directory where output files will be written",
    )
    parser.add_argument(
        "--out_type",
        choices=("lp", "smt2"),
        required=True,
        help="output format",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.input_dir.is_dir():
        raise SystemExit(
            "error: input directory does not exist: {}".format(args.input_dir)
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for input_path in sorted(args.input_dir.iterdir()):
            if input_path.is_file():
                print("input_path ", input_path)
                process_file(input_path, args.output_dir, args.out_type)
    except (OSError, ValueError) as error:
        raise SystemExit("error: {}".format(error))


if __name__ == "__main__":
    main()