#!/bin/sh

cp /srv/programs/support_script/service/home-autodisable.service       /etc/systemd/system/
cp /srv/programs/support_script/service/home-extbus-uart.service       /etc/systemd/system/
cp /srv/programs/support_script/service/home-extbus-udp.service        /etc/systemd/system/
cp /srv/programs/support_script/service/home-remap.service             /etc/systemd/system/
cp /srv/programs/support_script/service/home-motion-detector.service   /etc/systemd/system/


systemctl --system daemon-reload

systemctl enable home-autodisable.service
systemctl enable home-extbus-uart.service
systemctl enable home-extbus-udp.service
systemctl enable home-remap.service
systemctl enable home-motion-detector.service

systemctl start  home-autodisable.service
systemctl start  home-extbus-uart.service
systemctl start  home-extbus-udp.service
systemctl start  home-remap.service
systemctl start  home-motion-detector.service


