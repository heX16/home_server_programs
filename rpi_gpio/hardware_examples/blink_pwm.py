import RPi.GPIO as GPIO
import time

LED_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# Частота ШИМ 100 Гц
pwm = GPIO.PWM(LED_PIN, 100)
pwm.start(0)

try:
    while True:
        pwm.ChangeDutyCycle(90)  # 10% яркости
        time.sleep(2)
        pwm.ChangeDutyCycle(0)  # 100% яркости
        time.sleep(0.2)

except KeyboardInterrupt:
    pass

pwm.stop()
GPIO.cleanup()
