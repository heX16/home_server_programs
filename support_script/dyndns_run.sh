#!/bin/sh

wget --no-check-certificate -O - https://freedns.afraid.org/dynamic/update.php?WUIwVGJoUXdDUDcxVUlHemtEN1BxYndoOjE3ODM5NjYx
exit

systemctl start dyndns.service
sleep 3
systemctl status dyndns.service
