import argparse
import subprocess
import time
from enum import Enum, auto
from typing import Optional
from threading import Lock, Event

import RPi.GPIO as GPIO


class BlinkPattern(Enum):
    # Pattern names describe the flash rate (flashes per interval).
    # Patterns are defined in phases:
    # - BASE phase: base brightness (may include pauses between flashes)
    # - FLASH phase: flash brightness
    FLASH_1F_2S = auto()
    FLASH_2F_2S = auto()
    FLASH_3F_2S = auto()
    FLASH_4F_2S = auto()
    FLASH_5F_2S = auto()
    FLASH_10F_1S = auto()


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
    # LED pattern semantics:
    # Each blink pattern is a 2-phase cycle:
    # - BASE phase: keep base_brightness_pct for (period_ms - flash_pulse_ms)
    # - FLASH phase: keep flash_brightness_pct for flash_pulse_ms
    base_brightness_pct = 10.0
    flash_brightness_pct = 100.0
    flash_pulse_ms = 50

    flash_2s_period_ms = 2000
    inter_flash_pause_ms = 100
    flash_10f_1s_period_ms = 100

    flashes_in_2s_by_pattern = {
        BlinkPattern.FLASH_1F_2S: 1,
        BlinkPattern.FLASH_2F_2S: 2,
        BlinkPattern.FLASH_3F_2S: 3,
        BlinkPattern.FLASH_4F_2S: 4,
        BlinkPattern.FLASH_5F_2S: 5,
    }

    if blink_pattern in flashes_in_2s_by_pattern:
        period_ms = flash_2s_period_ms
        flash_count = flashes_in_2s_by_pattern[blink_pattern]
        phase_ms = t_ms % period_ms

        # One "slot" = one flash pulse + the pause that follows it.
        # The first N slots produce the flashes; the rest of the period is base.
        slot_ms = flash_pulse_ms + inter_flash_pause_ms
        flashes_block_ms = slot_ms * flash_count

        if phase_ms < flashes_block_ms:
            pos_in_slot = phase_ms % slot_ms
            if pos_in_slot < flash_pulse_ms:
                remaining_ms = flash_pulse_ms - pos_in_slot
                return remaining_ms / 1000.0, flash_brightness_pct
            remaining_ms = slot_ms - pos_in_slot
            return remaining_ms / 1000.0, base_brightness_pct

        remaining_ms = period_ms - phase_ms
        return remaining_ms / 1000.0, base_brightness_pct

    period_by_pattern_ms = {
        BlinkPattern.FLASH_10F_1S: flash_10f_1s_period_ms,
    }

    period_ms = period_by_pattern_ms[blink_pattern]
    flash_ms = flash_pulse_ms
    phase_ms = t_ms % period_ms

    if phase_ms < flash_ms:
        remaining_ms = flash_ms - phase_ms
        return remaining_ms / 1000.0, flash_brightness_pct

    remaining_ms = period_ms - phase_ms
    return remaining_ms / 1000.0, base_brightness_pct


def parse_blink_pattern(value: str) -> BlinkPattern:
    try:
        return BlinkPattern[value]
    except KeyError:
        allowed = ', '.join(p.name for p in BlinkPattern)
        raise argparse.ArgumentTypeError(
            f'Invalid blink pattern: {value}. Allowed values: {allowed}'
        )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Raspberry Pi status LED + shutdown button')
    parser.add_argument(
        '--test',
        type=parse_blink_pattern,
        metavar='BlinkPattern',
        help='Run the given BlinkPattern immediately (no button monitoring)',
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    pwm_hz = 100
    # Debounce for the interrupt callback (milliseconds)
    button_bouncetime_ms = 50

    args = parse_args(argv)
    test_pattern: Optional[BlinkPattern] = args.test
    test_mode = test_pattern is not None

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(options['led_pin'], GPIO.OUT)
    pull = GPIO.PUD_DOWN if options['button_is_inverted'] else GPIO.PUD_UP
    GPIO.setup(options['button_pin'], GPIO.IN, pull_up_down=pull)

    pwm = GPIO.PWM(options['led_pin'], pwm_hz)
    pwm.start(brightness_percent_to_duty(0))

    blink_pattern = test_pattern or BlinkPattern.FLASH_1F_2S

    # Button hold tracking via interrupts
    lock = Lock()
    loop_event = Event()
    button_pressed = False
    pressed_started_at: Optional[float] = None
    button_event_enabled = False

    if not test_mode:
        button_pressed = gpio_state_is_pressed(GPIO.input(options['button_pin']))
        pressed_started_at = time.monotonic() if button_pressed else None

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
            bouncetime=button_bouncetime_ms,
        )
        button_event_enabled = True

    if test_mode:
        print(f'rpi_status_gpio started (test mode: {blink_pattern.name})')
    else:
        print('rpi_status_gpio started')

    try:
        while True:
            now = time.monotonic()

            # --- Hold-to-shutdown ---
            hold_started_at: Optional[float] = None
            if not test_mode:
                with lock:
                    hold_started_at = pressed_started_at

                if blink_pattern == BlinkPattern.FLASH_1F_2S and hold_started_at is not None:
                    if (now - hold_started_at) >= options['hold_to_shutdown_s']:
                        blink_pattern = BlinkPattern.FLASH_10F_1S
                        print('Shutdown requested (button held)')
                        run_shutdown_command()

            now_ms = int(now * 1000.0) % 60_000
            pause_s, brightness = compute_pause_s_and_brightness(
                blink_pattern=blink_pattern,
                t_ms=now_ms,
            )
            set_brightness(pwm, brightness)

            if test_mode:
                time.sleep(pause_s)
            else:
                if hold_started_at is not None:
                    pause_s = min(pause_s, 0.2)

                loop_event.wait(timeout=pause_s)
                loop_event.clear()

    except KeyboardInterrupt:
        pass
    finally:
        try:
            if button_event_enabled:
                GPIO.remove_event_detect(options['button_pin'])
            pwm.stop()
        finally:
            GPIO.cleanup()


if __name__ == '__main__':
    main()

