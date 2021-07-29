#!/bin/bash

# chmod g+x set_access.sh
#cp set_access.sh /etc/cron.hourly/set_access.sh
echo Setting the access right.

cd /srv/config
sudo chown -R root:share *
sudo chmod -R g+rw *
# set for folders for group 'share' - Read,Write,Explore
find . -type d -exec sudo chmod g+rwx {} \;

cd /srv/programs
sudo chown -R root:share *
sudo chmod -R g+rw *
# set for folders for group 'share' - Read,Write,Explore
find . -type d -exec sudo chmod g+rwx {} \;

#find . -type f -name "*.sh" -exec sudo chown -R root: {} \;
#find . -type f -name "*.sh" -exec sudo chown :share {} \;
find . -type f -name "*.sh" -exec sudo chmod g+rx  {} \;
find . -type f -name "*.elf" -exec sudo chmod g+rx  {} \;

# WARN: hole in security!
#find . -type f -name "*.sh" -exec sudo chmod u+s  {} \;

cd /etc/openhab/
sudo chown -R root:share /etc/openhab
sudo chmod -R g+rw /etc/openhab
find . -type d -exec sudo chmod g+rwx {} \;

