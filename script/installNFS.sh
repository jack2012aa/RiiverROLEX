#!/bin/bash
apt update && apt install nfs-kernel-server

echo "setting NFS..."
mkdir -p /nfs_share
chmod 777 /nfs_share
sudo chown -R $USER:$USER /nfs_share
# Set white list
echo "rpcbind: 10.10.1.0/24" | sudo tee -a /etc/hosts.allow
sudo sed -i 's/-h 127.0.0.1//g' /etc/default/rpcbind

echo "/nfs_share 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)" >> /etc/exports
exportfs -a
systemctl restart nfs-kernel-server


