import subprocess
import time
from typing import Optional

import RPi.GPIO as GPIO


LED_PIN = 18
BUTTON_PIN = 4

PWM_HZ = 100

# Normal operation pattern:
# - Base brightness stays at 10%
# - A very short 100% flash happens once every 2 seconds
NORMAL_BASE_BRIGHTNESS = 10
NORMAL_FLASH_BRIGHTNESS = 100
NORMAL_FLASH_INTERVAL_S = 2.0
NORMAL_FLASH_DURATION_S = 0.06

# Button hold time to start shutdown
HOLD_TO_SHUTDOWN_S = 5.0

# Shutdown pattern: blink 10 times per second
SHUTDOWN_BLINK_HZ = 10.0

# Debounce: require stable input state for this duration
BUTTON_DEBOUNCE_S = 0.05

# Your wiring is inverted for LED brightness:
# - 100% brightness -> duty 0
# - 0% brightness   -> duty 100
LED_BRIGHTNESS_IS_INVERTED = True


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def brightness_percent_to_duty(percent: float) -> float:
    percent = _clamp(percent, 0.0, 100.0)
    if LED_BRIGHTNESS_IS_INVERTED:
        return 100.0 - percent
    return percent


def set_brightness(pwm: GPIO.PWM, percent: float) -> None:
    pwm.ChangeDutyCycle(brightness_percent_to_duty(percent))


def run_shutdown_command() -> None:
    # Note: this typically requires root privileges or sudo NOPASSWD.
    subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=False)


def main() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    pwm = GPIO.PWM(LED_PIN, PWM_HZ)
    pwm.start(brightness_percent_to_duty(0))

    shutdown_started = False

    now = time.monotonic()

    # Normal mode scheduling
    next_normal_flash_at = now + NORMAL_FLASH_INTERVAL_S
    flash_until_at: Optional[float] = None

    # Shutdown blink scheduling
    shutdown_toggle_every_s = 1.0 / (SHUTDOWN_BLINK_HZ * 2.0)
    shutdown_next_toggle_at: Optional[float] = None
    shutdown_blink_on = False

    # Button debounce + hold tracking (active-low button: 0 = pressed)
    raw_state = GPIO.input(BUTTON_PIN)
    debounced_state = raw_state
    last_raw_state = raw_state
    last_raw_change_at = now
    hold_started_at: Optional[float] = None

    print('rpi_status_gpio started')

    try:
        while True:
            now = time.monotonic()

            # --- Button debounce ---
            raw_state = GPIO.input(BUTTON_PIN)
            if raw_state != last_raw_state:
                last_raw_state = raw_state
                last_raw_change_at = now

            if (now - last_raw_change_at) >= BUTTON_DEBOUNCE_S and debounced_state != last_raw_state:
                debounced_state = last_raw_state
                if debounced_state == 0:
                    hold_started_at = now
                else:
                    hold_started_at = None

            # --- Hold-to-shutdown ---
            if not shutdown_started and hold_started_at is not None:
                if (now - hold_started_at) >= HOLD_TO_SHUTDOWN_S:
                    shutdown_started = True
                    shutdown_next_toggle_at = now
                    shutdown_blink_on = False
                    print('Shutdown requested (button held)')
                    run_shutdown_command()

            # --- LED patterns ---
            if shutdown_started:
                if shutdown_next_toggle_at is None or now >= shutdown_next_toggle_at:
                    shutdown_blink_on = not shutdown_blink_on
                    shutdown_next_toggle_at = now + shutdown_toggle_every_s
                    set_brightness(
                        pwm,
                        NORMAL_FLASH_BRIGHTNESS if shutdown_blink_on else NORMAL_BASE_BRIGHTNESS,
                    )
            else:
                if flash_until_at is not None and now >= flash_until_at:
                    flash_until_at = None
                    set_brightness(pwm, NORMAL_BASE_BRIGHTNESS)

                if flash_until_at is None and now >= next_normal_flash_at:
                    flash_until_at = now + NORMAL_FLASH_DURATION_S
                    next_normal_flash_at = now + NORMAL_FLASH_INTERVAL_S
                    set_brightness(pwm, NORMAL_FLASH_BRIGHTNESS)

                if flash_until_at is None:
                    set_brightness(pwm, NORMAL_BASE_BRIGHTNESS)

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            pwm.stop()
        finally:
            GPIO.cleanup()


if __name__ == '__main__':
    main()

