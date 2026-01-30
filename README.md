# Automatic Generation of Polynomial Symmetry Breakers
## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)


## Introduction

Symmetry in integer programming causes redundant search and is often handled with symmetry breaking constraints that remove as many equivalent solutions as possible. We propose an algebraic method which allows to generate a random family of polynomial inequalities which can be used as symmetry breakers. The method requires as input an arbitrary base polynomial and a group of permutations which is pecific to the integer program. The computations can be easily carried out in any major symbolic computation software. In order to test our approach, we describe a case study on near half-capacity 0-1 bin packing instances which exhibit substantial symmetries. We statically generate random quadratic breakers and add them to a baseline integer programming problem which we then solve with Gurobi. It turns out that simple symmetry breakers, especially combining few variables and permutations, most consistently reduce work time.

This repository accompanies the paper *NAutomatic Generation of Polynomial Symmetry Breaking Constraints* submitted to [ISSAC 2026](https://www.issac-conference.org/2026/). 

## Installation

### 1. Clone the repository

```
git clone [https://github.com/SAGE-Project/SAGE-GNN.git](https://github.com/merascu/PolynomialSymmetryBreakers.git)
cd PolynomialSymmetryBreakers
```

### 2. Install Dependencies

This project relies on the following libraries and tools:

- **Python (v3.9.6)**
- **Gurobi (v13.0.0)**

Please ensure you have these dependencies installed and configured correctly before running the project.

## Features and Usage

1. **Bin Packing LP Instance Generation**
   - Generate **0–1 bin packing** MILP instances in **LP format** (near half-capacity size classes).
   - Example:
     ```bash
     python bin_packing_problem_generator.py --B=100 --n=2000 --classes=5 --seed=2042
     ```
   - Code: 🔗 [bin_packing_problem_generator.py](./bin_packing_problem_generator.py)

2. **Augment LPs with Symmetry-Breaking Snippets**
   - Read a **base LP**, read all constraint snippet files from a directory, and **insert** each snippet **right before the `Binary` section**, producing one augmented LP per snippet.
   - Run:
     ```bash
     python gen_files_with_sbs.py base_lp_file="base.lp" sbs_dir="snippets/" gen_lp_files="out_lps/"
     ```
   - Code: 🔗 [gen_files_with_sbs.py](./gen_files_with_sbs.py)

3. **Batch Solve LPs with Gurobi**
   - Solve every `*.lp` in a directory using `gurobi_cl`, writing a `*.out` log and appending the `*.sol` solution to it.
   - Uses: `NonConvex=2`, `Presolve=0`, `Symmetry=0`, `WorkLimit=1800`.
   - Script: 🔗 [run_all_lp_with_Gurobi.sh](./run_all_lp_with_Gurobi.sh)

4. **Extract Solver Metrics to CSV**
   - Parse solver logs/outputs and extract: **file name**, **runtime**, **work units**, and **objective (if optimal)** into a CSV.
   - Run:
     ```bash
     python extract_to_csv.py path/to/logs results.csv --glob "*.out"
     ```
   - Code: 🔗 [extract_to_csv.py](./extract_to_csv.py)
5. **Johannes**

## License

This project is licensed under the [BSD 3-Clause License](LICENCE).
