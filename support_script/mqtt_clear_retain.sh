#!/bin/sh

# https://stackoverflow.com/questions/36729300/how-to-clear-all-retained-mqtt-messages-from-mosquitto
mosquitto_sub -h localhost -t "#" -v | while read line _; do mosquitto_pub -h localhost -t "$line" -r -n; done
