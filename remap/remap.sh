#!/bin/bash

cd `dirname $0`
chmod a+x mqtt_remap.py
#killall mqtt_remap.py

python3 mqtt_remap.py --verbose --config=/srv/config/remap.csv
