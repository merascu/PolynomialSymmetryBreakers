import os
import sys
import csv
import re

def extract_values(file_path):
    objective = None
    runtime = None

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if objective is None:
                m = re.search(r"Objective:\s*([-+]?\d*\.?\d+)", line)
                if m:
                    objective = m.group(1)

            if runtime is None:
                m = re.search(r"Runtime \(s\):\s*([-+]?\d*\.?\d+)", line)
                if m:
                    runtime = m.group(1)

            if objective is not None and runtime is not None:
                break

    return objective, runtime


def main():
    if len(sys.argv) != 2:
        print("Usage: python parse_out_to_csv.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    output_csv = "results.csv"

    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory")
        sys.exit(1)

    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["file_name", "objective", "runtime_seconds"])

        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".out"):
                file_path = os.path.join(directory, filename)
                objective, runtime = extract_values(file_path)
                writer.writerow([filename, objective, runtime])

    print(f"CSV file written to {output_csv}")


if __name__ == "__main__":
    main()