#!/bin/bash

apt update
DEBIAN_FRONTEND=noninteractive apt install python3 python3-pip build-essential

echo "setting huge pages..."
echo "vm.nr_hugepages=36000" > /etc/sysctl.d/90-rolex-hugepages.conf
sysctl -p /etc/sysctl.d/90-rolex-hugepages.conf

echo "setting memcached..."
sed -i 's/^-l .*/-l 0.0.0.0/' /etc/memcached.conf
systemctl restart memcached

echo "blocking IOMMU..."
sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt amd_iommu=off /' /etc/default/grub
update-grub


