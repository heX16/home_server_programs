#!/bin/sh

echo Restarting openhab
/etc/init.d/openhab2 restart
if [ $? -ne 0 ]
then
  echo "error!"
else
  echo "HA staring... Please wait 30 second."
fi

./set_access.sh

