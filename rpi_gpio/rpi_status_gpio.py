import subprocess
import time
from enum import Enum, auto
from typing import Optional
from threading import Lock, Event

import RPi.GPIO as GPIO



class BlinkPattern(Enum):
    PATTERN_1 = auto()
    SHUTDOWN = auto()


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


def compute_pause_s_and_brightness(
    *,
    blink_pattern: BlinkPattern,
    t_ms: int,
) -> tuple[float, float]:
    """
    Return (pause_s, brightness_percent) for the given pattern at time t_ms.

    t_ms is expected to be milliseconds within a minute (0..59999). The function is
    intentionally pure: it does not touch GPIO and does not maintain any state.
    """

    # Normal operation pattern:
    # - Base brightness stays at 10%
    # - A very short 100% flash happens once every 2 seconds
    NORMAL_BASE_BRIGHTNESS = 10
    NORMAL_FLASH_BRIGHTNESS = 100
    NORMAL_FLASH_INTERVAL_S = 2.0
    NORMAL_FLASH_DURATION_S = 0.06
    # Shutdown pattern: blink 10 times per second
    SHUTDOWN_BLINK_HZ = 10.0

    if blink_pattern == BlinkPattern.SHUTDOWN:
        half_period_ms = int(1000.0 / (SHUTDOWN_BLINK_HZ * 2.0))
        period_ms = half_period_ms * 2
        phase_ms = t_ms % period_ms

        if phase_ms < half_period_ms:
            remaining_ms = half_period_ms - phase_ms
            return remaining_ms / 1000.0, NORMAL_FLASH_BRIGHTNESS

        remaining_ms = period_ms - phase_ms
        return remaining_ms / 1000.0, NORMAL_BASE_BRIGHTNESS

    period_ms = int(NORMAL_FLASH_INTERVAL_S * 1000.0)
    flash_ms = int(NORMAL_FLASH_DURATION_S * 1000.0)
    phase_ms = t_ms % period_ms

    if phase_ms < flash_ms:
        remaining_ms = flash_ms - phase_ms
        return remaining_ms / 1000.0, NORMAL_FLASH_BRIGHTNESS

    remaining_ms = period_ms - phase_ms
    return remaining_ms / 1000.0, NORMAL_BASE_BRIGHTNESS


def main() -> None:
    PWM_HZ = 100
    # Debounce for the interrupt callback (milliseconds)
    BUTTON_BOUNCETIME_MS = 50

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(options['led_pin'], GPIO.OUT)
    pull = GPIO.PUD_DOWN if options['button_is_inverted'] else GPIO.PUD_UP
    GPIO.setup(options['button_pin'], GPIO.IN, pull_up_down=pull)

    pwm = GPIO.PWM(options['led_pin'], PWM_HZ)
    pwm.start(brightness_percent_to_duty(0))

    blink_pattern = BlinkPattern.PATTERN_1

    # Button hold tracking via interrupts
    lock = Lock()
    loop_event = Event()
    button_pressed = gpio_state_is_pressed(GPIO.input(options['button_pin']))
    pressed_started_at: Optional[float] = time.monotonic() if button_pressed else None

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

            if blink_pattern == BlinkPattern.PATTERN_1 and hold_started_at is not None:
                if (now - hold_started_at) >= options['hold_to_shutdown_s']:
                    blink_pattern = BlinkPattern.SHUTDOWN
                    print('Shutdown requested (button held)')
                    run_shutdown_command()

            now_ms = int(now * 1000.0) % 60_000
            pause_s, brightness = compute_pause_s_and_brightness(
                blink_pattern=blink_pattern,
                t_ms=now_ms,
            )
            set_brightness(pwm, brightness)

            if hold_started_at is not None:
                pause_s = min(pause_s, 0.2)

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

