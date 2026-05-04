#!/bin/bash
echo "fetching source code..."
cd /nfs_share
rm -rf RiverROLEX
git clone https://github.com/jack2012aa/RiverROLEX.git
chmod +x -R /nfs_share/RiverROLEX/script

echo "compiling..."
mkdir -p /nfs_share/RiverROLEX/build
cd /nfs_share/RiverROLEX/build
cmake ..
make -j


