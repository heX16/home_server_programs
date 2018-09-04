#!/bin/bash
# chmod g+x set_access.sh
#cp set_access.sh /etc/cron.hourly/set_access.sh
echo Setting the access right.

cd /srv/
sudo chown -R :share *
sudo chmod -R g+w *

# set for folders for group 'share' - Read,Write,Explore
find . -type d -exec sudo chmod g+rwx {} \;

#find . -type f -name "*.sh" -exec sudo chown -R root: {} \;
#find . -type f -name "*.sh" -exec sudo chown :share {} \;
find . -type f -name "*.sh" -exec sudo chmod g+rx  {} \;

# WARN: hole in security!
#find . -type f -name "*.sh" -exec sudo chmod u+s  {} \;

cd /etc/openhab2/
sudo chown -R :share *
sudo chmod -R g+w *
find . -type d -exec sudo chmod g+rwx {} \;

