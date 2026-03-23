#!/usr/bin/env bash

echo 'Setting the access rights.'

# /opt/hspro
if cd '/opt/hspro'; then
  sudo chown -R root:share .
  sudo chmod -R g+w .
  find . -type f -name '*.sh' -exec chmod a+rx '{}' \;
  find . -type f -name '*.elf' -exec chmod a+rx '{}' \;
  find . -type f -name '*.exec.??' -exec chmod a+rx '{}' \;
  find . -type f -name '*.exec.???' -exec chmod a+rx '{}' \;
else
  echo "WARN: cannot cd to /opt/hspro, skipping"
fi

if cd '/srv/config'; then
  sudo chown -R root:share .

  # Group can read/write; add execute only on dirs (and files that already had +x)
  # Others: no access
  sudo chmod -R g+rwX,o-rwx .

  # Ensure setgid on directories so new items inherit group "share"
  sudo find . -type d -exec chmod g+s '{}' \;
else
  echo 'WARN: cannot cd to /srv/config, skipping'
fi

# /etc/openhab2
if cd '/etc/openhab2'; then
  sudo chown -R openhab:share .
  sudo chmod -R g+w .
else
  echo "WARN: cannot cd to /etc/openhab2, skipping"
fi
