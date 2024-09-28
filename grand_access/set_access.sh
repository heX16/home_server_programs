#!/bin/bash

# chmod g+x set_access.sh

echo Setting the access right.

cd /srv/programs
sudo chown -R syncthing:share *
sudo chmod -R g+w *
find . -name "*.sh" -type f -exec chmod +rx "{}" \;
find . -name "*.elf" -type f -exec chmod +rx "{}" \;
find . -name "*.exec.??" -type f -exec chmod +rx "{}" \;
find . -name "*.exec.???" -type f -exec chmod +rx "{}" \;

cd /srv/config
sudo chown -R syncthing:share *
sudo chmod -R g+w *
find . -name "*.sh" -type f -exec chmod +rx "{}" \;

cd /etc/openhab2
sudo chown -R openhab:share *
sudo chmod -R g+w *

