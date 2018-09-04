#!/bin/bash

cd `dirname $0`
chmod a+x extbus_mqtt.elf
killall extbus_mqtt.elf

./extbus_mqtt.elf --mqtt=localhost --port=/dev/serial/by-path/platform-sunxi-ohci.2-usb-0:1:1.0-port0 --log --logmqtt &

# > ./mqtt_gate_uart2.log &
