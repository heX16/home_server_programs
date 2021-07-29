#!/bin/sh

sudo adduser --system --group syncthing
sudo usermod -G dialout -a syncthing
sudo usermod -G syncthing -a syncthing

groupadd share
usermod -a -G openhab,syncthing,share,sambashare,debian-transmission       share
usermod -a -G share openhab
usermod -a -G share syncthing
usermod -a -G share sambashare
usermod -a -G share debian-transmission
