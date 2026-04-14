#!/bin/bash
apt update && apt install nfs-kernel-server

echo "setting NFS and huge pages..."
mkdir -p /nfs_share
chmod 777 /nfs_share

echo "/nfs_share 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)" >> /etc/exports
exportfs -a
systemctl restart nfs-kernel-server


