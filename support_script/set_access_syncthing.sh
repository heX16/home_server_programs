#!/bin/bash
# chmod g+x set_access.sh
#cp set_access.sh /etc/cron.hourly/set_access.sh
echo Setting the access right.

sudo chown -R syncthing:share /home/syncthing
sudo chmod -R g+rw /home/syncthing
sudo chmod -R u+rw /home/syncthing

