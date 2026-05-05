#!/bin/bash
sudo apt update && apt install nfs-common
sudo mkdir -p /nfs_share

MOUNT="10.10.1.1:/nfs_share  /nfs_share  nfs  defaults  0  0" 
if ! grep -qF "$MOUNT" /etc/fstab; then
    echo "$MOUNT" | sudo tee -a /etc/fstab
fi
