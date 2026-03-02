#!/bin/sh

set -e

echo 'Installing Sys Monitor HTTP systemd units...'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_DIR=$(pwd)
UNIT_SRC_DIR="$SCRIPT_DIR/installation_and_config/systemd_cfg"
UNIT_DST_DIR="/etc/systemd/system"

UNITS="sysmon.socket sysmon.service sysmon-app.service"

for unit in $UNITS; do
  if [ ! -f "$UNIT_SRC_DIR/$unit" ]; then
    echo "Error: unit file not found: $UNIT_SRC_DIR/$unit" >&2
    exit 1
  fi
done

echo "Copying unit files to $UNIT_DST_DIR (sudo may prompt for password)..."
for unit in $UNITS; do
  sudo cp "$UNIT_SRC_DIR/$unit" "$UNIT_DST_DIR/$unit"
  sudo chmod 644 "$UNIT_DST_DIR/$unit"
done

echo "Updating WorkingDirectory in sysmon-app.service to: $APP_DIR"
sudo sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$APP_DIR|" "$UNIT_DST_DIR/sysmon-app.service"

echo 'Reloading systemd daemon...'
sudo systemctl daemon-reload

echo 'Enabling and starting socket unit sysmon.socket (services will start on demand)...'
sudo systemctl enable --now sysmon.socket

echo 'Done.'
echo 'You can check status with:'
echo '  sudo systemctl status sysmon.socket sysmon.service sysmon-app.service'

