#!/bin/sh -e
hostname=$1

if [ -z "$hostname" -o -z "$token" ]; then
  echo "Usage: token=<your-authentication-token> $0 your-name.dynv6.net"
  exit 1
fi

if [ -e /usr/bin/curl ]; then
  bin="curl -fsS"
elif [ -e /usr/bin/wget ]; then
  bin="wget -O-"
else
  echo "neither curl nor wget found"
  exit 1
fi

# send addresses to dynv6
$bin "http://ipv4.dynv6.com/api/update?hostname=$hostname&ipv4=auto&token=$token"
