#!/bin/sh

sudo mount /dev/disk/by-uuid/9adb8e47-ed70-4c5b-ac64-96f395c3d09c /mnt/rpi64
sudo mount /dev/disk/by-uuid/529c21d7-8095-4862-8b50-724de09cbb48 /mnt/rpi64backup

# 9adb8e47 - 64gb FLASH (f2fs)
# 529c21d7 - virtual disk for backup (ext4)
