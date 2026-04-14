#!/bin/bash
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


