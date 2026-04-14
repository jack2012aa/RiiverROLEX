#!/bin/bash
apt update && apt install nfs-common
echo "10.10.1.100:/nfs_share  /mnt/my_nfs  nfs  defaults  0  0" | sudo tee -a /etc/fstab
