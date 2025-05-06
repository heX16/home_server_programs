#!/bin/sh

adduser --system --group syncthing
usermod -G dialout -a syncthing
usermod -G syncthing -a syncthing

groupadd share
usermod -a -G openhab,syncthing,share,sambashare,debian-transmission       share
usermod -a -G share openhab
usermod -a -G share syncthing
usermod -a -G share sambashare
usermod -a -G share debian-transmission

usermod -aG syncthing,www-data share
usermod -aG share,www-data syncthing
usermod -aG share,syncthing,www-data root

usermod -aG syncthing www-data
# not secure: usermod -aG share www-data


