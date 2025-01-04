#!/usr/bin/python

import sys, time
from pyA20.gpio import gpio
from pyA20.gpio import port

gpio.init()
gpio.setcfg(port.PA18, gpio.OUTPUT)
gpio.setcfg(port.PA19, gpio.OUTPUT)
while True:
	gpio.output(port.PA18, gpio.HIGH)
	gpio.output(port.PA19, gpio.LOW)
	time.sleep(0.25)
	gpio.output(port.PA18, gpio.LOW)
	gpio.output(port.PA19, gpio.HIGH)
	time.sleep(0.25)
