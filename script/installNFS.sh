#!/bin/bash
apt update && apt install nfs-kernel-server

echo "setting NFS..."
mkdir -p /nfs_share
chmod 777 /nfs_share
sudo chown -R $USER:$USER /nfs_share
# Set white list
echo "rpcbind: 10.10.1.0/24" | sudo tee -a /etc/hosts.allow
sudo sed -i 's/-h 127.0.0.1//g' /etc/default/rpcbind

EXPORT_LINE="/nfs_share 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)"

if ! grep -qF "$EXPORT_LINE" /etc/exports; then
    echo "$EXPORT_LINE" | sudo tee -a /etc/exports
fi
exportfs -a
systemctl restart nfs-kernel-server

mkdir -p /nfs_share/workloads/uniform
mkdir -p /nfs_share/workloads/zipfian
mkdir -p /nfs_share/results
