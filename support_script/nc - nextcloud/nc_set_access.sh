#!/bin/bash

echo Setting the access right.

cd /home/nextcloud/hex/files

echo "Setting www-data:share for all"
sudo chown -R www-data:share *

echo "set to files - Read,Write"
sudo chmod -R u=rw,g=rw *

echo "set to folders - Read,Write,Explore"
find . -type d -exec sudo chmod g+rwx {} \;

