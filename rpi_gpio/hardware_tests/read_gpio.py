import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(4, GPIO.IN, GPIO.PUD_UP)

def button_callback(channel):
    state = GPIO.input(4)
    print("Press (1)" if state == 0 else "Unpress (0)")

GPIO.add_event_detect(4, GPIO.BOTH, callback=button_callback, bouncetime=50)

try:
    print("Ctrl+C for exit.")
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()

