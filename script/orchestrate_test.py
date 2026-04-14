import argparse
import logging
import os
import subprocess
import sys
from time import sleep

from fabric import Connection, ThreadingGroup

TIMEOUT_SEC = 10 * 60


def set_up(master: Connection, helper: Connection, workers: ThreadingGroup):
    logging.info("setting up...")
    # Check test data existence
    no_uniform = (
        "No such file"
        in master.run(
            "ls /nfs_share/workloads/uniform/load_randint_workload",
            hide=True,
            warn=True,
        ).stdout
    )
    no_zipfian = (
        "No such file"
        in master.run(
            "ls /nfs_share/workloads/zipfian/load_randint_workload",
            hide=True,
            warn=True,
        ).stdout
    )
    if no_uniform or no_zipfian:
        logging.info("generating data set...")
        result = master.run(
            "python3 /nfs_share/RiiverROLEX/script/generator.py", hide=True, warn=True
        )
        if "No such file" in result.stdout:
            logging.error("nfs_share not mounted or code is not clone correctly")
            sys.exit(1)
        elif "Done" not in result.stdout:
            logging.error("something wrong happens when generating data set")
            logging.error(result.stderr)
            sys.exit(1)

    # Create path
    workers.run("mkdir -p ~/debug", hide=True)

    # Initialize Memcached
    logging.info("initializing Memcached...")
    master.sudo("systemctl restart memcached", hide=True)
    master.run("sleep 1")
    result = master.run(
        "python3 /nfs_share/RiiverROLEX/script/reset_memcached.py", warn=True, hide=True
    )
    if "complete" not in result.stdout:
        logging.error("Memcached is not set up correctly")
        logging.error(result.stdout)
        sys.exit(1)


def run_test(
    master: Connection, helper: Connection, workers: ThreadingGroup, name: str
):
    dists = ["uniform", "zipfian"]
    workloads = ["a", "b", "c", "d", "e", "f"]
    executable = "/nfs_share/RiiverROLEX/build/ycsb_test"

    for dist in dists:
        for workload in workloads:
            logging.info(f"start running {dist} workload {workload}")
            command = f"{executable} {2 + len(workers)} 24 8 randint {dist} {workload}"
            if workload == "e":
                command += " 100"
            primary_log = (
                f"/nfs_share/results/primary_log_{dist}_workload{workload}_{name}.log"
            )
            master.sudo(
                f'{command} > "{primary_log}" 2>&1 &', hide=True, timeout=TIMEOUT_SEC
            )
            sleep(1)

            secondary_log = (
                f"/nfs_share/results/secondary_log_{dist}_workload{workload}_{name}.log"
            )
            helper.sudo(f'{command} > "{secondary_log}" 2>&1 &', hide=True)
            sleep(1)

            debug_log = f"~/debug/debug_{dist}_{workload}_{name}.log"
            result = workers.sudo(f'{command} > "{debug_log}"', hide=True, warn=True)

            def aggregate_test_result():
                logging.info("aggregating test results...")
                result_dir = f"results/{dist}_workload{workload}_{name}"
                os.makedirs(result_dir, exist_ok=True)
                try:
                    master.get(primary_log, os.path.join(result_dir, "primary.log"))
                    helper.get(secondary_log, os.path.join(result_dir, "secondary.log"))
                    i = 2
                    for worker in workers:
                        worker.get(
                            debug_log, os.path.join(result_dir, f"debug_log_{i}.log")
                        )
                        i += 1
                except:
                    logging.warning("failed to get log files")

            if result.failed:
                aggregate_test_result()
                raise RuntimeError("test failed")
            logging.info(f"{dist} workload {workload} completed")
            aggregate_test_result()

    logging.info("all tests are completed, parsing results...")
    subprocess.run("python parse_log.py")


def tear_down(master: Connection, helper: Connection, workers: ThreadingGroup):
    logging.info("tearing down...")
    master.sudo("pkill -9 ycsb_test", hide=True, warn=True)
    helper.sudo("pkill -9 ycsb_test", hide=True, warn=True)
    workers.sudo("pkill -9 ycsb_test", hide=True, warn=True)
    master.close()
    helper.close()
    workers.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        prog="Orchestrate ROLEX benchmarks", description="Orchestrate ROLEX benchmarks"
    )
    _ = parser.add_argument(
        "-e", "--endpoints", type=str, nargs="+", help="test servers' endpoints"
    )
    _ = parser.add_argument("-n", "--name", type=str, help="name of this test")

    args = parser.parse_args()
    endpoints: list[str] = args.endpoints
    if len(endpoints) < 2:
        logging.error(f"number of nodes should be greater than 1, got {len(endpoints)}")
        sys.exit(1)
    name: str = args.name

    logging.info("connecting to endpoints...")
    master = Connection(endpoints[0])
    helper = Connection(endpoints[1])
    workers = ThreadingGroup(*endpoints[2:])

    try:
        set_up(master, helper, workers)
        run_test(master, helper, workers, name)
    except Exception as e:
        logging.error(e)
    except KeyboardInterrupt:
        logging.info("stopping the test...")
    finally:
        tear_down(master, helper, workers)
