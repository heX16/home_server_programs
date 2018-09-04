#!/bin/sh

groupadd share
usermod -a -G openhab,syncthing,share,sambashare,debian-transmission       share
usermod -a -G share openhab
usermod -a -G share syncthing
usermod -a -G share sambashare
usermod -a -G share debian-transmission
