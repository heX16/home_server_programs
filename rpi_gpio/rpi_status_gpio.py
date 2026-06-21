import subprocess
import time
from typing import Optional
from threading import Lock, Event

import RPi.GPIO as GPIO


PWM_HZ = 100

# Normal operation pattern:
# - Base brightness stays at 10%
# - A very short 100% flash happens once every 2 seconds
NORMAL_BASE_BRIGHTNESS = 10
NORMAL_FLASH_BRIGHTNESS = 100
NORMAL_FLASH_INTERVAL_S = 2.0
NORMAL_FLASH_DURATION_S = 0.06

# Shutdown pattern: blink 10 times per second
SHUTDOWN_BLINK_HZ = 10.0

# Debounce for the interrupt callback (milliseconds)
BUTTON_BOUNCETIME_MS = 50

# Button hold time to start shutdown
# Your wiring is inverted for LED brightness:
# - 100% brightness -> duty 0
# - 0% brightness   -> duty 100
# Your wiring is inverted for the button:
# - False (default): active-low, pull-up, pressed when GPIO reads 0
# - True: active-high, pull-down, pressed when GPIO reads 1
options = {
    'led_pin': 18,
    'button_pin': 4,
    'hold_to_shutdown_s': 5.0,
    'led_brightness_is_inverted': True,
    'button_is_inverted': False,
}

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def brightness_percent_to_duty(percent: float) -> float:
    percent = _clamp(percent, 0.0, 100.0)
    if options['led_brightness_is_inverted']:
        return 100.0 - percent
    return percent


def gpio_state_is_pressed(state: int) -> bool:
    pressed_level = 1 if options['button_is_inverted'] else 0
    return state == pressed_level


def set_brightness(pwm: GPIO.PWM, percent: float) -> None:
    pwm.ChangeDutyCycle(brightness_percent_to_duty(percent))


def run_shutdown_command() -> None:
    # Note: this typically requires root privileges or sudo NOPASSWD.
    subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=False)


def compute_pause_s(
    *,
    shutdown_started: bool,
    flash_until_at: Optional[float],
    hold_started_at: Optional[float],
    shutdown_toggle_every_s: float,
) -> float:
    if shutdown_started:
        pause_s = 0.02
        if shutdown_toggle_every_s < pause_s:
            pause_s = shutdown_toggle_every_s
        return pause_s

    if flash_until_at is not None:
        return 0.01

    if hold_started_at is not None:
        return 0.5

    return 0.5


def main() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(options['led_pin'], GPIO.OUT)
    pull = GPIO.PUD_DOWN if options['button_is_inverted'] else GPIO.PUD_UP
    GPIO.setup(options['button_pin'], GPIO.IN, pull_up_down=pull)

    pwm = GPIO.PWM(options['led_pin'], PWM_HZ)
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

    # Button hold tracking via interrupts
    lock = Lock()
    loop_event = Event()
    button_pressed = gpio_state_is_pressed(GPIO.input(options['button_pin']))
    pressed_started_at: Optional[float] = now if button_pressed else None

    def button_callback(channel: int) -> None:
        nonlocal button_pressed, pressed_started_at
        state = GPIO.input(options['button_pin'])
        pressed_now = gpio_state_is_pressed(state)
        ts = time.monotonic()
        with lock:
            if pressed_now and not button_pressed:
                button_pressed = True
                pressed_started_at = ts
            elif not pressed_now and button_pressed:
                button_pressed = False
                pressed_started_at = None
        loop_event.set()

    GPIO.add_event_detect(
        options['button_pin'],
        GPIO.BOTH,
        callback=button_callback,
        bouncetime=BUTTON_BOUNCETIME_MS,
    )

    print('rpi_status_gpio started')

    try:
        while True:
            now = time.monotonic()

            # --- Hold-to-shutdown ---
            with lock:
                hold_started_at = pressed_started_at

            if not shutdown_started and hold_started_at is not None:
                if (now - hold_started_at) >= options['hold_to_shutdown_s']:
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

            pause_s = compute_pause_s(
                shutdown_started=shutdown_started,
                flash_until_at=flash_until_at,
                hold_started_at=hold_started_at,
                shutdown_toggle_every_s=shutdown_toggle_every_s,
            )

            loop_event.wait(timeout=pause_s)
            loop_event.clear()

    except KeyboardInterrupt:
        pass
    finally:
        try:
            GPIO.remove_event_detect(options['button_pin'])
            pwm.stop()
        finally:
            GPIO.cleanup()


if __name__ == '__main__':
    main()

