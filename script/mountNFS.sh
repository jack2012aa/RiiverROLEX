#!/bin/bash
apt update && apt install nfs-common
mkdir -p /nfs_share
echo "10.10.1.1:/nfs_share  /nfs_share  nfs  defaults  0  0" | sudo tee -a /etc/fstab
