#!/bin/bash

set -ex

bash installLibs.sh
bash installTestEnv.sh
bash mountNFS.sh
bash installMLNX.sh

echo "Rebooting to apply MLNX driver and GRUB changes..."
reboot
