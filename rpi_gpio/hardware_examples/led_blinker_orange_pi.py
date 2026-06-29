#!/usr/bin/env python
# -*- coding: utf-8 -*-

import OPi.GPIO as GPIO # https://github.com/Jeremie-C/OrangePi.GPIO
from time import sleep          # this lets us have a time delay

GPIO.setboard(GPIO.ZERO)    # Orange Pi PC board. See: https://github.com/Jeremie-C/OrangePi.GPIO/blob/1ee758716799c57ec6179ab93d0bbfa8f25ac18d/source/common.h#L23
GPIO.setmode(GPIO.BOARD)        # set up BOARD/BCM numbering
pinMyLed = 12
GPIO.setup(pinMyLed, GPIO.OUT)

try:
    print ("Press CTRL+C to exit")
    while True:
        GPIO.output(pinMyLed, 1)       # set port/pin value to 1/HIGH/True
        sleep(0.1)
        GPIO.output(pinMyLed, 0)       # set port/pin value to 0/LOW/False
        sleep(0.1)

        GPIO.output(pinMyLed, 1)       # set port/pin value to 1/HIGH/True
        sleep(0.1)
        GPIO.output(pinMyLed, 0)       # set port/pin value to 0/LOW/False
        sleep(0.1)

        sleep(0.5)

except (KeyboardInterrupt, SystemExit):
    GPIO.output(pinMyLed, 0)           # set port/pin value to 0/LOW/False
    GPIO.cleanup()              # Clean GPIO
    print ("Bye.")
