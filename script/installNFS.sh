#!/bin/bash
apt update && apt install nfs-kernel-server

echo "setting NFS and huge pages..."
mkdir -p /nfs_share
chmod 777 /nfs_share

echo "/nfs_share 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)" >> /etc/exports
exportfs -a
systemctl restart nfs-kernel-server

echo "fetching source code..."
cd /nfs_share
rm -rf RiiverROLEX
git clone https://github.com/jack2012aa/RiiverROLEX.git
chmod +x -R /nfs_share/RiiverROLEX/script

echo "compiling..."
mkdir -p /nfs_share/RiiverROLEX/build
cd /nfs_share/RiiverROLEX/build
cmake ..
make -j


