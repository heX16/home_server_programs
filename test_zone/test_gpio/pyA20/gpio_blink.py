#!/usr/bin/python

import sys, time
from pyA20.gpio import gpio
from pyA20.gpio import port

gpio.init()
gpio.setcfg(port.PA6, gpio.OUTPUT)
while True:
	gpio.output(port.PA6, gpio.HIGH)
	time.sleep(0.25)
	gpio.output(port.PA6, gpio.LOW)
	time.sleep(0.25)
