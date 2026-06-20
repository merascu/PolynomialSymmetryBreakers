#!/usr/bin/env python3
import argparse
import os
import re
from collections import OrderedDict

LABEL_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_]*):\s*(.*)$')
COMPARE_RE = re.compile(r'^(.*?)(<=|>=|=)\s*([-+]?\d+(?:\.\d+)?)\s*$')
TERM_RE = re.compile(r'([+-]?)\s*(?:(\d+)\s+)?(.+)$')
PRODUCT_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)$')
SQUARE_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\^\s*2$')
SPACE_RE = re.compile(r'\s+')


def clean_spaces(text: str) -> str:
    text = text.replace('[', ' ').replace(']', ' ')
    text = SPACE_RE.sub(' ', text).strip()
    text = text.replace('+ -', '- ')
    text = text.replace('- -', '+ ')
    text = text.replace('+ +', '+ ')
    return text.strip()


def split_terms(expr: str):
    expr = clean_spaces(expr)
    expr = expr.replace('-', '+ -')
    parts = [p.strip() for p in expr.split('+') if p.strip()]
    out = []
    for p in parts:
        m = TERM_RE.match(p)
        if not m:
            continue
        sign, coeff_str, body = m.groups()
        coeff = int(coeff_str) if coeff_str else 1
        if sign == '-':
            coeff *= -1
        out.append((coeff, clean_spaces(body)))
    return out


def z_name(a: str, b: str) -> str:
    x, y = sorted((a, b))
    return f'z_{x}_{y}'


def format_terms(terms):
    filtered = [(c, v) for c, v in terms if c != 0]
    if not filtered:
        return '0'
    pieces = []
    for i, (coeff, var) in enumerate(filtered):
        if coeff == 1:
            core = var
        elif coeff == -1:
            core = f'- {var}' if i > 0 else f'-{var}'
        else:
            core = f'{coeff} {var}'
        if i == 0:
            pieces.append(core)
        else:
            if coeff > 0:
                pieces.append(f'+ {core}')
            elif coeff == -1:
                pieces.append(core)
            else:
                pieces.append(f'- {abs(coeff)} {var}')
    text = ' '.join(pieces)
    text = text.replace('+ - ', '- ')
    text = text.replace('+ -', '- ')
    return clean_spaces(text)


class Linearizer:
    def __init__(self):
        self.next_label = 1
        self.pair_to_z = OrderedDict()

    def new_label(self) -> str:
        label = f'sb{self.next_label:06d}'
        self.next_label += 1
        return label

    def linearize_term(self, coeff: int, body: str):
        body = clean_spaces(body)
        m = SQUARE_RE.match(body)
        if m:
            return [(coeff, m.group(1))], [], False
        m = PRODUCT_RE.match(body)
        if not m:
            return [(coeff, body)], [], False
        a, b = m.groups()
        if a == b:
            return [(coeff, a)], [], True
        key = tuple(sorted((a, b)))
        z = self.pair_to_z.get(key)
        fresh = []
        if z is None:
            z = z_name(a, b)
            self.pair_to_z[key] = z
            fresh = [(z, key[0], key[1])]
        return [(coeff, z)], fresh, True

    def auxiliary_constraints(self, z: str, a: str, b: str):
        return [
            f'{self.new_label()}: {z} - {a} <= 0',
            f'{self.new_label()}: {z} - {b} <= 0',
            f'{self.new_label()}: {a} + {b} - {z} <= 1',
        ]

    def process_constraint(self, line: str):
        line = line.strip()
        if not line:
            return [], []

        label = None
        m = LABEL_RE.match(line)
        if m:
            label, body = m.groups()
        else:
            body = line
            label = self.new_label()

        body = clean_spaces(body)
        cm = COMPARE_RE.match(body)
        if not cm:
            return [f'{label}: {body}'], []

        lhs, op, rhs = cm.groups()
        terms = split_terms(lhs)

        new_terms = []
        created_pairs = []
        had_quadratic = False
        for coeff, term_body in terms:
            linear_terms, fresh, was_quadratic = self.linearize_term(coeff, term_body)
            new_terms.extend(linear_terms)
            created_pairs.extend(fresh)
            had_quadratic = had_quadratic or was_quadratic

        if had_quadratic:
            main_expr = format_terms(new_terms)
            main_line = f'{label}: {main_expr} {op} {rhs}'
        else:
            main_line = f'{label}: {body}'
        aux_lines = []
        seen = set()
        for z, a, b in created_pairs:
            key = (z, a, b)
            if key in seen:
                continue
            seen.add(key)
            aux_lines.extend(self.auxiliary_constraints(z, a, b))
        return [main_line] + aux_lines, created_pairs


def process_file(input_path: str, output_dir: str):
    linearizer = Linearizer()
    out_constraints = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            produced, _ = linearizer.process_constraint(line)
            out_constraints.extend(produced)

    base = os.path.splitext(os.path.basename(input_path))[0]
    constraints_path = os.path.join(output_dir, base + '_constraints.lp')
    vars_path = os.path.join(output_dir, base + '_new_variables.lp')

    with open(constraints_path, 'w', encoding='utf-8') as f:
        for line in out_constraints:
            f.write(clean_spaces(line) + '\n')

    with open(vars_path, 'w', encoding='utf-8') as f:
        for _, z in linearizer.pair_to_z.items():
            f.write(z + '\n')


def main():
    parser = argparse.ArgumentParser(description='Linearize quadratic terms in LP-like constraint files.')
    parser.add_argument('input_dir', help='Directory containing input files')
    parser.add_argument('output_dir', help='Directory where output files will be written')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    for name in sorted(os.listdir(args.input_dir)):
        input_path = os.path.join(args.input_dir, name)
        if os.path.isfile(input_path):
            process_file(input_path, args.output_dir)


if __name__ == '__main__':
    main()