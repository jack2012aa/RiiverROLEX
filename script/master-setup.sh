#!/bin/bash

set -ex

bash installLibs.sh
bash installTestEnv.sh
bash installNFS.sh
bash installMLNX.sh
bash compileSource.sh

echo "Rebooting to apply MLNX driver and GRUB changes..."
reboot
