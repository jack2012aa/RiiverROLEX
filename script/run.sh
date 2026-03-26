#!/bin/bash

# ================= Configuration Area =================
NODES=6
THREADS=24
MEM_NODES=3
KEYS=2700000
WORKLOADS=("a" "b" "c" "d" "e" "f" "g")
DISTRIBUTIONS=("uniform" "zipfian")

# Assuming your ycsb_test executable is in this directory
EXEC_DIR="/nfs_share/ROLEX/build"
# ==========================================

# Ensure results directory exists
mkdir -p /nfs_share/results

for dist in "${DISTRIBUTIONS[@]}"; do
    # Determine log filename abbreviation (u or z)
    if [ "$dist" == "uniform" ]; then
        dist_short="u"
    else
        dist_short="z"
    fi

    for wl in "${WORKLOADS[@]}"; do
        echo "=========================================================="
        echo "Preparing to run experiment: Workload ${wl^^}, Distribution $dist"
        echo "=========================================================="

        # 1. Clear old workloads
        echo "[Step 1] Clearing /nfs_share/workloads..."
        sudo rm -rf /nfs_share/workloads/*

        # 2. Generate new test dataset (Using Here-Document to input Python parameters automatically)
        echo "[Step 2] Generating test dataset (This may take a few minutes)..."
        python3 /nfs_share/ROLEX/script/generator.py <<EOF
$NODES
$THREADS
$KEYS
$wl
$dist
EOF

        # If workload is e, create an empty txn file
        if [ "$wl" == "e" ]; then
            echo "Detected Workload E, creating empty transaction file..."
            touch /nfs_share/workloads/txn_randint_workloade
        fi

        # 3 & 4. Restart Memcached and initialize counter
        echo "[Step 3 & 4] Resetting Memcached..."
        sudo systemctl restart memcached
        sleep 1 # Wait slightly for memcached to start
        python3 -c "
import socket
s = socket.socket()
s.connect(('127.0.0.1', 11211))
s.sendall(b'set serverNum 0 0 1\r\n0\r\n')
print('Memcached serverNum counter initialization complete!')
"

        # Prepare execution parameters (If workload is e, append 100 at the end)
        if [ "$wl" == "e" ]; then
            CMD_ARGS="6 24 8 randint e 100"
        else
            CMD_ARGS="6 24 8 randint $wl"
        fi

        # ================= Start Concurrent Execution =================
        echo "[Step 5-7] Starting all nodes to execute YCSB test..."

        # Node 0 (Local background execution, redirect to log)
        cd $EXEC_DIR
        sudo ./ycsb_test $CMD_ARGS > "/nfs_share/results/6_24_${MEM_NODES}_${dist_short}_${wl}.log" 2>&1 &

        sleep 1 # Ensure Node 0 (master node) has started and is waiting for barrier

        # Node 1 (Remote SSH background execution, redirect to lf_log)
        ssh -o StrictHostKeyChecking=no node-1 "cd $EXEC_DIR && sudo $EXEC_DIR/ycsb_test $CMD_ARGS" > "/nfs_share/results/6_24_${MEM_NODES}_${dist_short}_${wl}_lf.log" 2>&1 &

        sleep 1

        # Nodes 2 to 5 (Remote SSH background execution, redirect output to debug_log instead of /dev/null)
        for i in {2..5}; do
            ssh -o StrictHostKeyChecking=no node-$i " cd $EXEC_DIR && sudo $EXEC_DIR/ycsb_test $CMD_ARGS" > "/nfs_share/results/debug_node_${i}.log" 2>&1 &
        done

        # Key command: Wait for all background processes (&) above to finish
        echo "Test in progress, waiting for all nodes to finish..."
        wait

        echo "Workload ${wl^^} ($dist) test completed successfully!"
        echo ""
        sleep 3 # Let the network and OS buffer slightly before the next experiment starts
    done
done

echo "Congratulations! All automated tests have finished executing!"
echo "Now you can run python3 parse_logs.py to see the final CSV or table!"
