#!/bin/bash

set -ex

echo "installing dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  nfs-kernel-server \
  memcached \
  libmemcached-dev \
  libnuma-dev \
  build-essential \
  cmake \
  git \
  python3 \
  python3-pip

echo "setting NFS and huge pages..."
mkdir -p /nfs_share
chmod 777 /nfs_share

echo "/nfs_share 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)" >> /etc/exports
exportfs -a
systemctl restart nfs-kernel-server

echo "vm.nr_hugepages=36000" > /etc/sysctl.d/90-rolex-hugepages.conf
sysctl -p /etc/sysctl.d/90-rolex-hugepages.conf

echo "setting memcached..."
sed -i 's/^-l .*/-l 0.0.0.0/' /etc/memcached.conf
systemctl restart memcached

echo "fetching source code..."
cd /nfs_share
rm -rf RiiverROLEX
git clone https://github.com/jack2012aa/RiiverROLEX.git
chmod +x -R /nfs_share/RiiverROLEX/script

echo "installing other dependencies and MLNX driver..."
systemctl stop opensmd.service || true
systemctl mask opensmd.service

/nfs_share/RiiverROLEX/script/installLibs.sh
/nfs_share/RiiverROLEX/script/installMLNX.sh

echo "blocking IOMMU..."
sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt amd_iommu=off /' /etc/default/grub
update-grub

echo "compiling..."
mkdir -p /nfs_share/RiiverROLEX/build
cd /nfs_share/RiiverROLEX/build
cmake ..
make -j

echo "Rebooting to apply MLNX driver and GRUB changes..."
reboot
