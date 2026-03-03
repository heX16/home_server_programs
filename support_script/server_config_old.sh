#!/bin/sh


# i2c
#NOTE: sudo raspi-config.  'Advanced Options' >> 'I2C' >> 'Yes'
#sudo apt-get install -y python-smbus i2c-tools

#sudo apt-get install iputils-arping
#sudo chmod u+s /usr/bin/arping



# WIP!!!

# add “openhab” to the group of users who can run sudo commands
#sudo adduser openhab sudo

## create: /etc/sudoers.d/openhub_srv_ctrl
#/etc/sudoers.d/openhub_srv_ctrl
#'''
## Allow openhab user to execute shutdown, poweroff, and systemctl commands
#openhab   ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/poweroff, /sbin/systemctl, /sbin/reboot
#'''

## all files in this directory should be mode 0440
#chmod 440 /etc/sudoers.d/openhub_srv_ctrl
