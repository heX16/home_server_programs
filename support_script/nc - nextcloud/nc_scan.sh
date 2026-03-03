#!/bin/bash

if systemctl show nextcloud_scan.service | grep -q 'ActiveState=active'; then
  # grep -q 'ActiveState=activating';...
  echo "Scan service already in work"
  exit
fi


sudo systemctl start nextcloud_scan.service

# sudo -u www-data /usr/bin/php -f /var/www/nextcloud/occ files:scan --all --verbose --no-interaction
# echo -e "\a"; sleep 1; echo -e "\a"; sleep 1; echo -e "\a"

exit


# systemd.
# можно использовать??? ExecCondition=

# ЕСЛИ:
#   systemctl show media-data2tb.automount
#     СОДЕРЖИТ:
#     ActiveState=active
#     SubState=waiting
# ТОГДА: не запускаем сканирование и не запускаем обслуживание.

# sudo -u www-data php ...occ
occ --output=json user:list
occ user:lastseen username

occ files:scan --path="user/folder..."
