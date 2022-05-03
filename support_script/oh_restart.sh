#!/bin/sh

echo Restarting openhab
service openhab start restart
./set_access.sh

