# Automatic Generation of Polynomial Symmetry Breakers
## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Features and Usage](#features-and-usage)
- [License](#license)


## Introduction

Symmetry in integer programming causes redundant search and is often handled with symmetry breaking constraints that remove as many equivalent solutions as possible. We propose an algebraic method which allows to generate a random family of polynomial inequalities which can be used as symmetry breakers. The method requires as input an arbitrary base polynomial and a group of permutations which is pecific to the integer program. The computations can be easily carried out in any major symbolic computation software. The method was tested on a case study on near half-capacity 0-1 bin packing instances which exhibit substantial symmetries. We statically generate random quadratic breakers and add them to a baseline integer programming problem which we then solve with Gurobi.

We performed an experimental evaluation of this method using several mathematical programming solvers ([Gurobi](https://www.gurobi.com/), [CPLEX](https://www.ibm.com/products/ilog-cplex-optimization-studio), [SCIP](https://www.scipopt.org/), and [Hexaly](https://www.hexaly.com/)) and satisfiability modulo theories (SMT) solvers ([Z3](https://github.com/z3prover/z3)).

It turns out that the effectiveness of polynomial symmetry breaking is strongly solver-dependent. Compact quadratic breaker families can improve performance, whereas linearization, large breaker sets, or solver reformulations may offset these gains through increased model size or less favorable search behavior. These results suggest that automatically generated symmetry breakers should be evaluated in a solver-aware manner rather than treated as solver-independent additions to a model.

This repository accompanies the experimental paper *When Algebraic Symmetry Breaking Meets Solvers: An Experimental Study* submitted to [LPAR 2026](https://easychair.org/smart-program/LPAR-26/).

## LPAR Results

Each directory, coresponding to a solver used in the experiments, in the archive [LPAR2026-eval](https://drive.google.com/file/d/1gd1dYetik97MqHwIUlDquI-EnoURzFco/view?usp=sharing) contains two subfolders:
1. `lp/SMT2` contains the LP/SMT2 files with the problem instances, together with the corresponding `.out` files containing the solutions.
2. `csv` contains the CSV files with the time required to find a solution and, where applicable, additional statistics. These files correspond to the `.out` files mentioned above.

## Installation

### 1. Clone the repository

```
git clone https://github.com/merascu/PolynomialSymmetryBreakers.git
cd PolynomialSymmetryBreakers
```

### 2. Install Dependencies

This project relies on the following libraries and tools:

- **Python (v3.9.6)**
- **Gurobi (v13.0.0), Academic License**
- **CPLEX (v22.1.1.0), Academic License**
- **SCIP (v10.0.2), Academic License**
- **Z3 (v4.15.3)**
- **Emacs (v29.1 or better)**
- **OCaml (v5.3.0 or better) and opam**

Please ensure you have these dependencies installed and configured correctly before running the project.

## Features and Usage

1. **Bin Packing Instance Generation**
   - **LP files**
      - Generates **0–1 bin packing** MILP instances in **LP format**.
      - Run:
        ```bash
        python bin_packing_problem_generator.py --B=100 --n=2000 --classes=5 --seed=2042
        ```
      - Code: 🔗 [bin_packing_problem_generator_LP.py](./src/bin_packing_problem_generator_LP.py)
   - **SMT files**
      - Generates **0–1 bin packing** instances in **SMT2 format**.
   - Run:
      - Example:
        ```bash
        python bin_packing_problem_generator_SMT2.py --B=100 --n=2000 --classes=5 --seed=2042
        ```
      - Code: 🔗 [bin_packing_problem_generator_SMT2.py](./src/bin_packing_problem_generator_SMT2.py)
2. **Generate Symmetry Breakers**
   - Takes an instance of the bin packing problem and generates a suite of random symmetry breakers (10 for each combination of shape, number of variables, and number of permutations).
   
   1. Install the **re** library using opam. This needs to be done only once.
      ```bash
      opam install re
      ```
   2. Extract the source code from the literate program format ([quadratic-breakers.org](./src/quadratic-breakers.org)): either from the terminal with
      ```bash
      emacs --batch -l org quadratic-breakers.org -f org-babel-tangle
      ```
      or by opening the ([quadratic-breakers.org](./src/quadratic-breakers.org)) file in Emacs and calling the `org-babel-tangle` function (as `M-x org-babel-tangle` or `C-c C-v C-t`).

   3. Compile the extracted source code with
      ```bash
      ocamlbuild -package re breakers.native
      ```
   4. Call the complied program as:
      ```bash
      ./breakers.native <FILES>
      ```
      where `FILES` are randomly generated bin packing instances (in
      either `LP` or `SMT` format). The output will be in `LP` format by
      default, but this can be changed by using the `--smt2` command line
      option. Moreover, the `--repetitions <INT>` option can be used to
      control how many breaker files should be generated for each input
      file.
   - **Warnings**
       - The program assumes that the object sizes are given as a
         comment at the start of the `LP` or `SMT` file. Moreover, it
         assumes that the objects sizes are ordered ascendingly.

4. **Augment problems in LP/SMT2 format with Symmetry-Breaking Constraints**
   - Augments the bin packing base model (`base.lp`) with symmetry-breaking constraints and writes the resulting LP models to `prob_with_sbs/`.  Each file in `sbs/` contains a *family* of symmetry breakers that is inserted into the base model to produce a corresponding augmented LP file.
   - Run:
     ```bash
     python gen_files_with_sbs.py base_lp_file="base.lp" sbs_dir="sbs/" gen_lp_files="prob_with_sbs/"
     ```
   - Code: 🔗 [gen_files_with_sbs_LP.py](./src/gen_files_with_sbs_LP.py)

5. **Batch Solve LPs with Gurobi**
   - Solves with Gurobi every model saved in an `lp` file. Saves the results into `lp_out_files` directory.
   - Parameters: `gurobi_cl` is run with the parameters `NonConvex=2`, `Presolve=0`, `Symmetry=0`, `WorkLimit=1800`.
   - Run:
     ```bash
     ./run_all_lp_with_Gurobi.sh <lp_out_files>
     ```
   - Code: 🔗 [run_all_lp_with_Gurobi.sh](./scripts/run_all_lp_with_Gurobi.sh)

6. **Extract Solver Metrics to CSV**
   - Parses Gurobi one gurobi file at a time and extracts into a CSV file, by columns:
      - **`filename`**:
        Name of the parsed log file.
      - **`status`**  
        Solver termination status:
           - `"Optimal solution found"` if an optimal solution was proven.
           - `"Time limit reached"` if the run stopped due to the time limit.        
      - **`objective`**  
        The value of the optimal solution value **only if** the log contains a line of the form:        
      - **`gap`**  
        Final optimality gap reported by Gurobi, extracted from the line:  
      - **`work_units`**  
        Gurobi **work units** which are a solver-defined metric computed in an deterministic manner intended to be more comparable across machines than raw runtime.
      - **`runtime_seconds`**  
        Total runtime in seconds, extracted from the line:        
      - **`initial_gap`**  
        The first gap value reported in the progress table (root/early stage) which approximates the initial difficulty of the instance.
      - **`simplex_iters`**  
        Total number of simplex iterations performed.
      - **`nodes`**  
        Total number of branch-and-bound nodes explored, extracted from:  
   - Run:
      ```bash
      python extract_to_csv.py in_path="path/to/dir_with_out_files" out_csv="results.csv"
      ```
   - Code: 🔗 [extract_to_csv.py](./src/extract_to_csv.py)


## License

This project is licensed under the [BSD 3-Clause License](LICENCE).
