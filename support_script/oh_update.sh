#!/bin/sh

/etc/init.d/openhab2 stop
apt update
apt install --only-upgrade openhab2
./set_access
/etc/init.d/openhab2 start
