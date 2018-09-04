#!/bin/bash

cd `dirname $0`
chmod a+x extbus_mqtt.elf
killall extbus_mqtt.elf

./extbus_mqtt.elf --mqtt=localhost --port=UDP4:192.168.1.255 --log --logmqtt > ./mqtt_gate_upd.log &

