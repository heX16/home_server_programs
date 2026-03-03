#!/bin/sh

service openhab stop
apt update
apt install --only-upgrade openhab
./set_access
service openhab start

