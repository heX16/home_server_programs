#!/bin/sh

echo 'UPD IPv4:'
netstat -np -u --listen -4 | grep -v 'Active Internet connections'

echo ''
echo 'UPD IPv6:'
netstat -np -u --listen -6 | grep -v 'Active Internet connections'

echo ''
echo 'IPv4:'
netstat -np -t --listen -4 | grep -v 'Active Internet connections'

echo ''
echo 'IPv6:'
netstat -np -t --listen -6 | grep -v 'Active Internet connections'


