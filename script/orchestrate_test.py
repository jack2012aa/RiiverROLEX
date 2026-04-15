import argparse
import logging
import os
import subprocess
import sys
from time import sleep

from fabric import Connection, ThreadingGroup

TIMEOUT_SEC = 10 * 60
master_promise = None
helper_promise = None
workers_promise = None


def set_up(master: Connection, helper: Connection, workers: ThreadingGroup):
    logging.info("setting up...")
    # Check test data existence
    no_uniform = (
        "No such file"
        in master.run(
            "ls /nfs_share/workloads/uniform/load_randint_workload",
            warn=True,
            hide=True,
        ).stderr
    )
    no_zipfian = (
        "No such file"
        in master.run(
            "ls /nfs_share/workloads/zipfian/load_randint_workload",
            warn=True,
            hide=True,
        ).stderr
    )
    if no_uniform or no_zipfian:
        logging.info("generating data set...")
        result = master.run(
            f"python3 /nfs_share/RiiverROLEX/script/generator.py -n {2 + len(workers)}",
            warn=True,
        )
        if "No such file" in result.stderr:
            logging.error(result.stderr)
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
    global master_promise, helper_promise, workers_promise
    dists = ["uniform", "zipfian"]
    workloads = ["a", "b", "c", "d", "e", "f"]
    working_dir = "/nfs_share/RiiverROLEX/build"
    executable = f"{working_dir}/ycsb_test"

    for dist in dists:
        for workload in workloads:
            set_up(master, helper, workers)
            command = f"{executable} {2 + len(workers)} 24 8 randint {dist} {workload}"
            if workload == "e":
                command += " 100"
            logging.info(f"start running test command: {command}")
            primary_log = (
                f"/nfs_share/results/primary_log_{dist}_workload{workload}_{name}.log"
            )
            master_promise = master.run(
                f"cd {working_dir} && {command} > {primary_log} 2>&1",
                asynchronous=True,
                timeout=TIMEOUT_SEC,
                hide=True,
                warn=True,
            )
            sleep(1)

            secondary_log = (
                f"/nfs_share/results/secondary_log_{dist}_workload{workload}_{name}.log"
            )
            helper_promise = helper.run(
                f"cd {working_dir} && {command} > {secondary_log} 2>&1",
                hide=True,
                warn=True,
                asynchronous=True,
                timeout=TIMEOUT_SEC,
            )
            sleep(1)

            debug_log = f"~/debug/debug_{dist}_{workload}_{name}.log"
            workers_promise = workers.run(
                f'cd {working_dir} && {command} > "{debug_log}"',
                hide=True,
                warn=True,
                asynchronous=True,
                timeout=TIMEOUT_SEC,
            )

            while not master_promise.runner.process_is_finished:
                try:
                    tail_result = master.run(
                        f"tail -n 1 {primary_log}", hide=True, warn=True
                    )
                    if tail_result.stdout.strip():
                        print(
                            f"\rProgress: {tail_result.stdout.strip()}",
                            end="",
                            flush=True,
                        )
                except Exception:
                    pass
                sleep(5)

            result = master_promise.join()
            helper_promise.join()

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
                raise RuntimeError(result.stderr.strip())
            logging.info(f"{dist} workload {workload} completed")
            aggregate_test_result()

    logging.info("all tests are completed, parsing results...")
    subprocess.run("python parse_log.py")


def tear_down(master: Connection, helper: Connection, workers: ThreadingGroup):
    logging.info("tearing down...")
    try:
        master.sudo("pkill -9 ycsb_test", hide=True, warn=True)
        master_promise.join()
    except:
        pass
    try:
        helper.sudo("pkill -9 ycsb_test", hide=True, warn=True)
        helper_promise.join()
    except:
        pass
    try:
        workers.sudo("pkill -9 ycsb_test", hide=True, warn=True)
    except:
        pass
    master.close()
    helper.close()
    workers.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        prog="Orchestrate ROLEX benchmarks", description="Orchestrate ROLEX benchmarks"
    )
    _ = parser.add_argument(
        "-e",
        "--endpoints",
        type=str,
        required=True,
        nargs="+",
        help="test servers' endpoints",
    )
    _ = parser.add_argument(
        "-n", "--name", type=str, required=True, help="name of this test"
    )

    args = parser.parse_args()
    endpoints: list[str] = args.endpoints
    logging.info(endpoints)
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


if __name__ == "__main__":
    main()
