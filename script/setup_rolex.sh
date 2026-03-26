#!/bin/bash

# --- Basic Configurations ---
NFS_SERVER_IP="10.10.1.1"
SHARE_DIR="/nfs_share"
ROLEX_DIR="$SHARE_DIR/ROLEX"
INSTALL_FLAG="/var/rolex_install_done"
MY_HOSTNAME=$(hostname -s)
WORKER_NODES=("node-1" "node-2" "node-3" "node-4" "node-5")

# Ensure this script is executed ONLY on node-0
if [ "$MY_HOSTNAME" != "node-0" ]; then
    echo "Error: This script must be run from node-0 as the master controller."
    exit 1
fi

echo "--- ROLEX Automated Configuration (Master Node: $MY_HOSTNAME) ---"

# ==========================================================
# Phase 1: Initial Installation and Reboot (Execute only once)
# ==========================================================
if [ ! -f "$INSTALL_FLAG" ]; then
    echo "[Step 1] Setting up node-0 (NFS Server & Dependencies)..."

    # 1. Setup NFS Server & Memcached on node-0
    sudo apt-get update && sudo apt-get install -y nfs-kernel-server memcached libmemcached-dev
    
    sudo mkdir -p $SHARE_DIR
    sudo chmod 777 $SHARE_DIR
    
    # Avoid duplicate entries in /etc/exports
    if ! grep -q "$SHARE_DIR" /etc/exports; then
        echo "$SHARE_DIR 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)" | sudo tee -a /etc/exports
    fi
    sudo exportfs -a
    sudo systemctl restart nfs-kernel-server

    # 2. Git Clone (If directory does not exist)
    if [ ! -d "$ROLEX_DIR" ]; then
        cd $SHARE_DIR
        git clone https://github.com/River861/ROLEX.git
    fi

    # 3. Install dependencies on node-0 BEFORE compiling
    echo "Installing drivers and setting GRUB on node-0..."
    sudo chmod +x -R $ROLEX_DIR/script
    cd $ROLEX_DIR
    sudo ./script/installLibs.sh

    # [NEW] Configure Memcached to listen on all interfaces so worker nodes can connect
    echo "Configuring Memcached to listen on 0.0.0.0..."
    sudo sed -i 's/^-l .*/-l 0.0.0.0/' /etc/memcached.conf
    sudo systemctl restart memcached
    
    # [HOTFIX] Mask opensmd.service completely to prevent installMLNX.sh from hanging during systemctl restart
    echo "Masking opensmd.service to prevent installation hang..."
    sudo systemctl mask opensmd.service
    
    sudo ./script/installMLNX.sh
    
    # Configure IOMMU Passthrough (For AMD d6515)
    sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt amd_iommu=off /' /etc/default/grub
    sudo update-grub

    # 4. Compile ROLEX right after setting up node-0
    # At this point, node-0 has OFED and all required libraries installed, so compilation will succeed.
    echo "[Step 2] Compiling ROLEX on node-0..."
    mkdir -p $ROLEX_DIR/build
    cd $ROLEX_DIR/build
    cmake ..
    make -j

    # 5. Configure worker nodes via SSH
    echo "[Step 3] Configuring worker nodes via SSH..."
    for NODE in "${WORKER_NODES[@]}"; do
        echo "Configuring $NODE..."
        ssh -o StrictHostKeyChecking=no $NODE "
            # Setup NFS client
            sudo apt-get update && sudo apt-get install -y nfs-common memcached libmemcached-dev;
            sudo mkdir -p $SHARE_DIR;
            if ! grep -q '$NFS_SERVER_IP:$SHARE_DIR' /etc/fstab; then
                echo '$NFS_SERVER_IP:$SHARE_DIR $SHARE_DIR nfs defaults 0 0' | sudo tee -a /etc/fstab;
            fi;
            sudo mount -a;
            
            # Install dependencies and MLNX drivers
            cd $ROLEX_DIR;
            sudo ./script/installLibs.sh;
            
            # [HOTFIX] Mask opensmd on worker nodes as well
            sudo systemctl mask opensmd.service;
            sudo ./script/installMLNX.sh;
            
            # Configure IOMMU Passthrough
            sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=\"/GRUB_CMDLINE_LINUX_DEFAULT=\"iommu=pt amd_iommu=off /' /etc/default/grub;
            sudo update-grub;
            sudo touch $INSTALL_FLAG;
        "
    done

    # Mark node-0 as done
    sudo touch $INSTALL_FLAG

    # 6. Reboot all nodes
    echo "[Step 4] Initial installation complete. Rebooting worker nodes first, then node-0..."
    for NODE in "${WORKER_NODES[@]}"; do
        ssh -o StrictHostKeyChecking=no $NODE "sudo reboot" &
    done
    sleep 3
    sudo reboot
    exit 0
fi

# ==========================================================
# Phase 2: Post-reboot Initialization (Execute after every reboot)
# ==========================================================
echo "[Step 5] Executing post-reboot environment initialization..."

# 1. Configure Hugepages and Memcached on worker nodes via SSH
for NODE in "${WORKER_NODES[@]}"; do
    echo "Configuring hugepages and memcached on $NODE..."
    ssh -o StrictHostKeyChecking=no $NODE "
        sudo sysctl -w vm.nr_hugepages=36000;
        sudo systemctl restart memcached;
    "
done

# 2. Configure Hugepages and Memcached on node-0
echo "Configuring hugepages and memcached on node-0..."
sudo sysctl -w vm.nr_hugepages=36000
sudo systemctl restart memcached
sleep 2

# 3. Initialize Memcached serverNum (Executed only on node-0)
echo "Initializing Memcached serverNum..."
python3 -c "
import socket
s = socket.socket()
s.connect(('127.0.0.1', 11211))
s.sendall(b'set serverNum 0 0 1\r\n0\r\n')
"
echo "Memcached serverNum initialization complete!"

echo "--- All configurations are complete! ---"
