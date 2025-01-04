#!/bin/sh -e

# http://freedns.afraid.org

token=$1
file=/tmp/freedns.addr6.txt
[ -e $file ] && old=`cat $file`

if [ -z "$token" ]; then
  echo "Usage: script.sh token"
  echo "  only for http://freedns.afraid.org"
  echo "  token is ~'WUIwVGJoUXdDUDcxVUlHemtEN1BxYndoOjE3ODM5NjY0' string"
  exit 1
fi

if [ -n "$device" ]; then
  device="dev $device"
fi
address=$(ip -6 addr list scope global $device | grep -v " fd" | sed -n 's/.*inet6 \([0-9a-f:]\+\).*/\1/p' | head -n 1)

if [ -e /usr/bin/curl ]; then
  wget="curl -fsS"
elif [ -e /usr/bin/wget ]; then
  wget="wget -O-"
else
  echo "neither curl nor wget found"
  exit 1
fi

if [ -z "$address" ]; then
  echo "no IPv6 address found"
  exit 1
fi

# address with netmask
current=$address

if [ "$old" = "$current" ]; then
  echo "IPv6 address unchanged"
  exit
fi

# send addresses to http://freedns.afraid.org
$wget "http://freedns.afraid.org/dynamic/update.php?$token&address=$address"

# save current address
echo $current > $file