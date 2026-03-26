import random
import os
import multiprocessing
import time
import sys
import array
import numpy as np

# Base path configuration
PATH = "/nfs_share/workloads/"
OS_PATH = os.path.expanduser(PATH)
os.makedirs(OS_PATH, exist_ok=True)

# Use Python's built-in C-style array to save memory
global_all_keys = None


def generate_partition(args):
    client_id, wl, start_idx, end_idx, keys_per_thread, dist, total_keys = args

    # 1. Generate load file
    load_file_path = os.path.join(OS_PATH, f"load_randint_workload{wl}{client_id}")
    with open(load_file_path, "w") as f:
        for i in range(start_idx, end_idx):
            f.write(f"INSERT {global_all_keys[i]}\n")

    # 2. Generate txn file (with Zipfian support)
    txn_file_path = os.path.join(OS_PATH, f"txn_randint_workload{wl}{client_id}")

    # [Optimization] If Zipfian, generate all skewed index arrays at once using numpy
    if dist == "zipfian":
        # a=1.5 is a standard high-skew parameter. Subtracting 1 and taking modulo folds the infinite tail back into a valid range
        zipf_indices = (np.random.zipf(1.5, keys_per_thread) - 1) % total_keys

    with open(txn_file_path, "w") as f:
        for i in range(keys_per_thread):
            # Select Key based on the distribution mode
            if dist == "zipfian":
                key = global_all_keys[zipf_indices[i]]
            else:
                key = random.choice(global_all_keys)

            # Generate a random probability to determine the operation (faster than random.choices)
            p = random.random()

            # --- YCSB Workloads ---
            if wl == "a":  # 50% Read, 50% Update (Modify existing data)
                op = "READ" if p < 0.5 else "UPDATE"
                f.write(f"{op} {key}\n")

            elif wl == "b":  # 95% Read, 5% Update
                op = "READ" if p < 0.95 else "UPDATE"
                f.write(f"{op} {key}\n")

            elif wl == "c":  # 100% Read
                f.write(f"READ {key}\n")

            elif wl == "d":  # 95% Read, 5% Insert (Insert new data)
                if p < 0.95:
                    f.write(f"READ {key}\n")
                else:
                    new_key = random.getrandbits(60)
                    f.write(f"INSERT {new_key}\n")

            elif wl == "e":  # 95% Scan, 5% Insert
                if p < 0.95:
                    scan_length = random.randint(1, 100)
                    f.write(f"SCAN {key} {scan_length}\n")
                else:
                    new_key = random.getrandbits(60)
                    f.write(f"INSERT {new_key}\n")

            elif (
                wl == "f"
            ):  # 50% Read, 50% Read-Modify-Write (Simplified as Update here)
                if p < 0.5:
                    op = "READ"
                    f.write(f"{op} {key}\n")
                else:
                    op = "INSERT"
                    if dist == "uniform":
                        key = (1 << 60) + (i * 256) + int(client_id)
                    f.write(f"{op} {key}\n")

            elif (
                wl == "g"
            ):  # [Custom] 50% Read, 50% Insert (Most stressful structural destruction test)
                if p < 0.5:
                    f.write(f"READ {key}\n")
                else:
                    new_key = random.getrandbits(60)
                    f.write(f"INSERT {new_key}\n")

    return True


def main():
    global global_all_keys

    print("=== YCSB Pro Generator (Zipfian & Custom Workloads) ===")

    try:
        NUM_NODES = int(input("Num nodes (e.g., 6): "))
        THREADS_PER_NODE = int(input("Threads per node (e.g., 24): "))
        KEYS_PER_THREAD = int(input("Keys per thread (e.g., 2700000): "))
        wl = input("Target workload (a, b, c, d, e, f, or g): ").strip().lower()
        dist = input("Distribution ('uniform' or 'zipfian'): ").strip().lower()
    except ValueError:
        print("Invalid input.")
        sys.exit(1)

    if wl not in ["a", "b", "c", "d", "e", "f", "g"] or dist not in [
        "uniform",
        "zipfian",
    ]:
        print("Error: Invalid workload or distribution type.")
        sys.exit(1)

    TOTAL_CLIENTS = NUM_NODES * THREADS_PER_NODE
    TOTAL_KEYS = TOTAL_CLIENTS * KEYS_PER_THREAD

    print(f"\n[Info] Workload: {wl.upper()} | Distribution: {dist.upper()}")
    print(f"[Info] Total threads: {TOTAL_CLIENTS}, Total keys: {TOTAL_KEYS}")

    start_time = time.time()

    # 1. Generate shared Key array
    print("\n[Step 1] Generating base key array (Memory Optimized)...")
    global_all_keys = array.array(
        "Q", (random.getrandbits(60) for _ in range(TOTAL_KEYS))
    )

    # 2. Generate load file for training
    print("\n[Step 2] Generating base load file for training...")
    base_load_path = os.path.join(OS_PATH, f"load_randint_workload{wl}")
    with open(base_load_path, "w") as f:
        for key in global_all_keys:
            f.write(f"INSERT {key}\n")

    # 3. Prepare multiprocessing tasks
    print(f"\n[Step 3] Preparing {TOTAL_CLIENTS} partition tasks...")
    tasks = []
    for i in range(TOTAL_CLIENTS):
        start_idx = i * KEYS_PER_THREAD
        end_idx = start_idx + KEYS_PER_THREAD
        tasks.append((i, wl, start_idx, end_idx, KEYS_PER_THREAD, dist, TOTAL_KEYS))

    # 4. Launch multi-core generation
    workers = min(multiprocessing.cpu_count(), 16)
    print(f"\n[Step 4] Launching {workers} workers to generate files...")

    with multiprocessing.Pool(processes=workers) as pool:
        for i, _ in enumerate(pool.imap_unordered(generate_partition, tasks), 1):
            print(f"\rProgress: {i}/{len(tasks)} files generated...", end="")

    end_time = time.time()
    print(
        f"\n\nDone! Generated {TOTAL_KEYS} ops in {end_time - start_time:.2f} seconds."
    )


if __name__ == "__main__":
    main()
