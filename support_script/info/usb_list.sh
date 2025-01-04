#!/bin/sh


echo "usb-devices: =============="
usb-devices

echo "lsusb: ================="
lsusb

echo "lsblk (disks): ================="
lsblk
rem sudo blkid

echo "Serial: =================="

ls /dev/serial/by-path/

