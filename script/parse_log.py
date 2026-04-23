import argparse
import os
import re


def parse_rolex_logs(base_dir):
    # 1. Regex patterns to extract performance metrics from primary.log (Node 0)
    metrics_patterns = {
        "TP_Mops": re.compile(r"cluster throughput\s+([\d\.]+)\s*Mops", re.IGNORECASE),
        "CAS_Fail": re.compile(
            r"avg\. lock/cas fail cnt:\s*([\d\.\-nan]+)", re.IGNORECASE
        ),
        "Sibling_Read": re.compile(
            r"read sibling leaf rate:\s*([\d\.\-nan]+)", re.IGNORECASE
        ),
        "Leaf_Retry": re.compile(
            r"read leaf retry rate:\s*([\d\.\-nan]+)", re.IGNORECASE
        ),
        "Spec_Read_Rate": re.compile(
            r"speculative read rate:\s*([\d\.\-nan]+)", re.IGNORECASE
        ),
        "Spec_Read_Correct": re.compile(
            r"correct ratio of speculative read:\s*([\d\.\-nan]+)", re.IGNORECASE
        ),
        "Cache_MB": re.compile(r"syn cache size:\s*([\d\.]+)\s*MB", re.IGNORECASE),
        "p50_Lat": re.compile(r"p50 latency\s*:\s*([\d\.]+)\s*ns", re.IGNORECASE),
        "p99_Lat": re.compile(r"p99 latency\s*:\s*([\d\.]+)\s*ns", re.IGNORECASE),
    }

    # 2. Regex pattern to extract leaf_cnt distribution from secondary.log (Node 1)
    leaf_cnt_pattern = re.compile(r"leaf_cnt=(\d+) ratio=([\d\.]+);")

    # 3. Recursively find all directories containing 'primary.log'
    exp_dirs = []
    for root, dirs, files in os.walk(base_dir):
        if "primary.log" in files:
            exp_dirs.append(root)

    if not exp_dirs:
        print(
            f"Error: No 'primary.log' files found in any subdirectories of {base_dir}"
        )
        return

    print(f"Found {len(exp_dirs)} experiment directories. Starting to parse...\n")

    experiments = []

    for exp_dir in exp_dirs:
        # Initialize default values for the row
        exp_data = {
            "Name": exp_dir.split("_")[-1],
            "Dir_Name": os.path.basename(exp_dir),
            "Dist": "Unknown",
            "WL": "N/A",
            "TP_Mops": "N/A",
            "p50_Lat": "N/A",
            "p99_Lat": "N/A",
            "CAS_Fail": "N/A",
            "Sibling_Read": "N/A",
            "Leaf_Retry": "N/A",
            "Spec_Read_Rate": "N/A",
            "Spec_Read_Correct": "N/A",
            "Cache_MB": "N/A",
            "Leaf_Distribution": "N/A",
        }
        name_match = re.search(r"workload[a-zA-Z0-9]+_(.+)", exp_data["Dir_Name"])
        if name_match:
            exp_data["Name"] = name_match.group(1).strip()

        # Try to infer Distribution and Workload from the directory name
        # e.g., "results/uniform_workloada_mytest" -> Dist: Uniform, WL: A
        match = re.search(
            r"(uniform|zipfian)_workload([a-zA-Z0-9]+)",
            exp_data["Dir_Name"],
            re.IGNORECASE,
        )
        if match:
            exp_data["Dist"] = match.group(1).capitalize()
            exp_data["WL"] = match.group(2).upper()

        primary_path = os.path.join(exp_dir, "primary.log")
        secondary_path = os.path.join(exp_dir, "secondary.log")

        # Parse primary.log
        with open(primary_path, "r") as f:
            content = f.read()
            for metric_name, pattern in metrics_patterns.items():
                matches = pattern.findall(content)
                if matches:
                    exp_data[metric_name] = matches[-1]

        # Parse secondary.log
        if os.path.exists(secondary_path):
            with open(secondary_path, "r") as f:
                content = f.read()
                lf_lines = [line for line in content.split("\n") if "leaf_cnt=" in line]

                if lf_lines:
                    start_line = lf_lines[1] if len(lf_lines) > 1 else lf_lines[0]
                    end_line = lf_lines[-1]

                    start_matches = leaf_cnt_pattern.findall(start_line)
                    end_matches = leaf_cnt_pattern.findall(end_line)

                    # Format as L4:86%
                    fmt_start = ",".join(
                        [
                            f"L{cnt}:{float(ratio) * 100:.0f}%"
                            for cnt, ratio in start_matches
                        ]
                    )
                    fmt_end = ",".join(
                        [
                            f"L{cnt}:{float(ratio) * 100:.0f}%"
                            for cnt, ratio in end_matches
                        ]
                    )

                    exp_data["Leaf_Distribution"] = (
                        f"Start[{fmt_start}] -> End[{fmt_end}]"
                    )

        experiments.append(exp_data)

    # 4. Sort experiments (by Distribution, then Workload)
    experiments.sort(key=lambda x: (x["Dist"], x["WL"], x["Dir_Name"]))

    # 5. Print table
    print("=" * 145)
    header = f"{'Name':<8} | {'Dist':<8} | {'WL':<3} | {'TP(Mops)':<8} | {'p50(ns)':<8} | {'p99(ns)':<8} | {'CAS_Fail':<8} | {'Sibling':<8} | {'Retry':<8} | {'SpecRate':<8} | {'SpecCorr':<8} | {'Cache(MB)':<9} | {'Leaf_Dist (Start -> End)'}"
    print(header)
    print("-" * 145)

    for exp in experiments:
        row = (
            f"{exp['Name']:<8} | {exp['Dist']:<8} | {exp['WL']:<3} | "
            f"{exp['TP_Mops']:<8} | {exp['p50_Lat']:<8} | {exp['p99_Lat']:<8} | "
            f"{exp['CAS_Fail']:<8} | {exp['Sibling_Read']:<8} | {exp['Leaf_Retry']:<8} | "
            f"{exp['Spec_Read_Rate']:<8} | {exp['Spec_Read_Correct']:<8} | {exp['Cache_MB']:<9} | {exp['Leaf_Distribution']}"
        )
        print(row)

    print("=" * 145)
    print(
        f"Parsing complete! Successfully parsed {len(experiments)} experiment records.\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse ROLEX benchmark logs from specified directory."
    )
    parser.add_argument(
        "log_dir",
        type=str,
        nargs="?",
        default="./results",
        help="Target directory containing the test result folders (default: ./results)",
    )
    args = parser.parse_args()

    target_path = os.path.abspath(args.log_dir)
    if not os.path.isdir(target_path):
        print(f"Error: The specified path '{target_path}' is not a valid directory.")
    else:
        parse_rolex_logs(target_path)
