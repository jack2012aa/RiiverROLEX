"""6 machines"""

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.emulab as elab

# cloud-init config
master_cloud_config = """#cloud-config
# Dependencies
package_update: true
packages:
  - nfs-kernel-server
  - memcached
  - libmemcached-dev
  - libnuma-dev
  - build-essential
  - cmake
  - git
  - python3
  - python3-pip

write_files:
  # NFS
  - path: /etc/exports
    content: |
      /nfs_share 10.10.1.0/24(rw,sync,no_root_squash,no_subtree_check)
    append: true
  # Memcached
  - path: /etc/sysctl.d/90-rolex-hugepages.conf
    content: |
      vm.nr_hugepages=36000

runcmd:
  # NFS
  - mkdir -p /nfs_share
  - chmod 777 /nfs_share
  - exportfs -a
  - systemctl restart nfs-kernel-server

  # Memcached
  - sed -i 's/^-l .*/-l 0.0.0.0/' /etc/memcached.conf
  - systemctl restart memcached

  # ROLEX
  - cd /nfs_share
  - git clone https://github.com/jack2012aa/RiiverROLEX.git
  - chmod +x -R /nfs_share/ROLEX/script

  # Other dependencies
  - systemctl mask opensmd.service # Prevent collision
  - /nfs_share/ROLEX/script/installLibs.sh
  - /nfs_share/ROLEX/script/installMLNX.sh

  # Unlimit IOMMU
  - sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt amd_iommu=off /' /etc/default/grub
  - update-grub

  # Compile
  - mkdir -p /nfs_share/ROLEX/build
  - cd /nfs_share/ROLEX/build && cmake .. && make -j

# Restart to use the new driver and iommu setting
power_state:
  mode: reboot
  message: "Cloud-init finished, rebooting to apply MLNX and GRUB changes"
  condition: True
"""

worker_cloud_config = """#cloud-config
package_update: true
packages:
  - nfs-common
  - memcached
  - libmemcached-dev
  - libnuma-dev
  - build-essential
  - python3
  - python3-pip

mounts:
  - [ "10.10.1.1:/nfs_share", "/nfs_share", "nfs", "defaults", "0", "0" ]

write_files:
  - path: /etc/sysctl.d/90-rolex-hugepages.conf
    content: |
      vm.nr_hugepages=36000

runcmd:
  # Wait for mounting
  - while [ ! -f /nfs_share/ROLEX/script/installLibs.sh ]; do sleep 5; done

  - systemctl mask opensmd.service
  - /nfs_share/ROLEX/script/installLibs.sh
  - /nfs_share/ROLEX/script/installMLNX.sh

  - sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt amd_iommu=off /' /etc/default/grub
  - update-grub

power_state:
  mode: reboot
  message: "Worker init finished, rebooting to apply MLNX and GRUB changes"
  condition: True
"""

def generate_setup_cmd(yaml_content):
    return """#!/bin/bash
cat << 'EOF' > /etc/cloud/cloud.cfg.d/99-rolex-custom.cfg
%s
EOF

cloud-init clean
cloud-init init
cloud-init modules -m config
cloud-init modules -m final
""" % yaml_content

pc = portal.Context()
request = pc.makeRequestRSpec()

NODE_COUNT = 2
HARDWARE_TYPE = 'r650'
IMAGE = 'urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU18-64-STD'

lan = request.LAN('rdma-lan')
lan.bandwidth = 100000000

for i in range(NODE_COUNT):
    name = "node-%d" % (i)
    node = request.RawPC(name)
    node.hardware_type = HARDWARE_TYPE
    node.disk_image = IMAGE
    
    iface = node.addInterface("if1")
    iface.addAddress(pg.IPv4Address("10.10.1.%d" % (i + 1), "255.255.255.0"))
    lan.addInterface(iface)

    if i == 0:
        nfs_bs = node.Blockstore("nfs-data", "/nfs_share")
        nfs_bs.size = "350GB"
        node.addService(pg.Execute(shell="sh", command="sudo chmod 777 /nfs_share"))
        node.addService(pg.Execute(shell="bash", command=generate_setup_cmd(master_cloud_config)))
    else:
        node.addService(pg.Execute(shell="bash", command=generate_setup_cmd(worker_cloud_config)))
        
pc.printRequestRSpec(request)
