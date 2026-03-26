import os
import re
import glob
from collections import defaultdict


def parse_rolex_logs(log_dir="/rfs_share/results"):
    experiments = defaultdict(dict)

    # 1. Ensure Regex supports the three-number format: <#node>_<#thread>_<#mem_node>_<u|z>_<workload>_[lf].log
    filename_pattern = re.compile(r"^(\d+)_(\d+)_(\d+)_([uz])_([a-zA-Z]+)(_lf)?\.log$")

    # 2. Regex patterns to extract performance metrics from Node 0
    metrics_patterns = {
        "TP_Mops": re.compile(r"cluster throughput ([\d\.]+) Mops"),
        "CAS_Fail": re.compile(r"avg\. lock/cas fail cnt: ([\d\.\-nan]+)"),
        "Sibling_Read": re.compile(r"read sibling leaf rate: ([\d\.\-nan]+)"),
        "Leaf_Retry": re.compile(r"read leaf retry rate: ([\d\.\-nan]+)"),
        "Spec_Read_Rate": re.compile(r"speculative read rate: ([\d\.\-nan]+)"),
        "Spec_Read_Correct": re.compile(
            r"correct ratio of speculative read: ([\d\.\-nan]+)"
        ),
        "Cache_MB": re.compile(r"consumed cache size = ([\d\.]+) MB"),
    }

    # Regex pattern to extract leaf_cnt distribution from Node 1
    leaf_cnt_pattern = re.compile(r"leaf_cnt=(\d+) ratio=([\d\.]+);")

    # 3. Scan all log files
    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    if not log_files:
        print("Error: No .log files found! Please check the execution directory.")
        return

    print(f"Found {len(log_files)} log files. Starting to parse...\n")

    for filepath in log_files:
        filename = os.path.basename(filepath)
        match = filename_pattern.match(filename)

        if not match:
            continue

        # Extract experiment configuration
        node, thread, mem_node, dist_code, workload, is_lf = match.groups()
        dist = "Uniform" if dist_code == "u" else "Zipfian"
        workload = workload.upper()

        # Define Unique Key (including mem_node)
        exp_key = (mem_node, dist, workload, node, thread)

        if exp_key not in experiments:
            experiments[exp_key] = {
                "Mem": mem_node,
                "Dist": dist,
                "WL": workload,
                "Node": node,
                "Thread": thread,
                "TP_Mops": "N/A",
                "CAS_Fail": "N/A",
                "Sibling_Read": "N/A",
                "Leaf_Retry": "N/A",
                "Spec_Read_Rate": "N/A",
                "Spec_Read_Correct": "N/A",
                "Cache_MB": "N/A",
                "Leaf_Distribution": "N/A",
            }

        with open(filepath, "r") as f:
            content = f.read()

            if is_lf:
                # This is the LF log from Node 1, find all lines containing leaf_cnt
                lf_lines = [line for line in content.split("\n") if "leaf_cnt=" in line]

                if lf_lines:
                    # Grab the 2nd line (index 1), if there is only 1 line, grab the 1st
                    start_line = lf_lines[1] if len(lf_lines) > 1 else lf_lines[0]
                    # Grab the last line
                    end_line = lf_lines[-1]

                    start_matches = leaf_cnt_pattern.findall(start_line)
                    end_matches = leaf_cnt_pattern.findall(end_line)

                    # Format as L4:86% (remove intermediate spaces to save width)
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

                    # Combine into Start -> End string
                    experiments[exp_key]["Leaf_Distribution"] = (
                        f"Start[{fmt_start}] -> End[{fmt_end}]"
                    )
            else:
                # This is the main log from Node 0
                for metric_name, pattern in metrics_patterns.items():
                    matches = pattern.findall(content)
                    if matches:
                        experiments[exp_key][metric_name] = matches[-1]

    # 4. Sort and print plain text table
    sorted_exps = sorted(
        experiments.values(),
        key=lambda x: (int(x["Mem"]), x["Dist"], x["WL"], int(x["Node"])),
    )

    # Set table width, allocating more space for the Start->End column
    print("=" * 155)
    header = f"{'Mem':<3} | {'Dist':<7} | {'WL':<2} | {'Node':<4} | {'Thrd':<4} | {'TP(Mops)':<8} | {'CAS_Fail':<8} | {'Sibling':<8} | {'Retry':<8} | {'SpecRate':<8} | {'SpecCorr':<8} | {'Cache(MB)':<9} | {'Leaf_Dist (Start -> End)'}"
    print(header)
    print("-" * 155)

    for exp in sorted_exps:
        row = (
            f"{exp['Mem']:<3} | {exp['Dist']:<7} | {exp['WL']:<2} | {exp['Node']:<4} | {exp['Thread']:<4} | "
            f"{exp['TP_Mops']:<8} | {exp['CAS_Fail']:<8} | {exp['Sibling_Read']:<8} | {exp['Leaf_Retry']:<8} | "
            f"{exp['Spec_Read_Rate']:<8} | {exp['Spec_Read_Correct']:<8} | {exp['Cache_MB']:<9} | {exp['Leaf_Distribution']}"
        )
        print(row)

    print("=" * 155)
    print(
        f"Parsing complete! Successfully merged {len(sorted_exps)} experiment records.\n"
    )


if __name__ == "__main__":
    parse_rolex_logs()
