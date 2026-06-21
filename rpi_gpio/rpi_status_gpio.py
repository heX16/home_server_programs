import argparse
import os
import signal
import subprocess
import time
from enum import Enum, auto
from functools import partial
from typing import Optional
from threading import Event

import RPi.GPIO as GPIO

try:
    import yaml
except ImportError:
    yaml = None

from button_state import ButtonEvent, ButtonState


class BlinkPattern(Enum):
    # Pattern names describe the flash rate (flashes per interval).
    # Patterns are defined in phases:
    # - BASE phase: base brightness (may include pauses between flashes)
    # - FLASH phase: flash brightness (100% for FLASH_*, 0% for BLACK_*)
    FLASH_1F_2S = auto()
    FLASH_2F_2S = auto()
    FLASH_3F_2S = auto()
    FLASH_4F_3S = auto()
    FLASH_5F_3S = auto()
    FLASH_10F_1S = auto()
    BLACK_1F_2S = auto()
    BLACK_2F_2S = auto()
    BLACK_3F_2S = auto()
    BLACK_4F_3S = auto()
    BLACK_5F_3S = auto()
    BLACK_10F_1S = auto()

    @classmethod
    def from_name(cls, value: str) -> 'BlinkPattern':
        return cls[value.upper()]


# Button enabled:
# - True (default): monitor button pin and support hold-to-shutdown
# - False: LED only, no button GPIO or hold-to-shutdown
# Your wiring is inverted for LED brightness:
# - 100% brightness -> duty 0
# - 0% brightness   -> duty 100
# Your wiring is inverted for the button:
# - False (default): active-low, pull-up, pressed when GPIO reads 0
# - True: active-high, pull-down, pressed when GPIO reads 1
# Internet connectivity check intervals in main mode (seconds between checks):
# - when internet is available (status 'inet'): every 10 minutes
# - when internet is not available: every 1 minute
# LED blink patterns for internet status:
# - 'inet': full internet access
# - 'local': local network only
# - 'none': no connection (also used for 'fail' and unknown statuses)
# Button hold actions (ButtonEvent that triggers each action):
# - 'RELEASED_HOLD_2S': release after 2-4s hold
# - 'HOLD_5S': still pressed at 5s
# - 'none': disabled
options = {
    'button': True,
    'led_pin': 18,
    'button_pin': 4,
    'internet_check_interval_s': 600.0,
    'internet_check_no_inet_interval_s': 60.0,
    'led_brightness_is_inverted': True,
    'button_is_inverted': False,
    'button_shutdown': 'HOLD_5S',
    'button_reboot': '',
    'blink_pattern_inet': 'FLASH_1F_2S',
    'blink_pattern_local': 'FLASH_3F_2S',
    'blink_pattern_none': 'FLASH_5F_3S',
}

loop_event = Event()


def systemd_shutdown_in_progress() -> bool:
    """
    Return True if systemd is in the shutdown/reboot phase.

    We intentionally rely on /run markers (tmpfs) so the check still works even
    after normal filesystems are unmounted.
    """
    shutdown_dir = '/run/systemd/shutdown'
    scheduled = '/run/systemd/shutdown/scheduled'
    return os.path.isdir(shutdown_dir) or os.path.exists(scheduled)


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


def button_callback(button_state: ButtonState, channel: int) -> None:
    gpio_state = GPIO.input(options['button_pin'])
    pressed_now = gpio_state_is_pressed(gpio_state)
    ts = time.monotonic()
    button_state.update_from_gpio(pressed_now, ts)
    loop_event.set()


def set_brightness(pwm: GPIO.PWM, percent: float) -> None:
    pwm.ChangeDutyCycle(brightness_percent_to_duty(percent))


def run_shutdown_command() -> None:
    # Note: this typically requires root privileges or sudo NOPASSWD.
    subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=False)


def run_reboot_command() -> None:
    subprocess.run(['sudo', 'reboot'], check=False)


# Internet check mode: 'nmcli' or 'ping'
internet_check_mode: str = 'nmcli'


def _check_via_nmcli() -> str:
    try:
        result = subprocess.run(
            ['nmcli', 'networking', 'connectivity'],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return 'fail'

    if result.returncode != 0:
        return 'fail'

    connectivity = result.stdout.strip().lower()
    if connectivity == 'full':
        return 'inet'
    if connectivity in ('limited', 'portal'):
        return 'local'
    if connectivity in ('none', 'unknown'):
        return 'none'
    return 'none'


def _has_default_gateway() -> bool:
    try:
        result = subprocess.run(
            ['ip', 'route'],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False

    if result.returncode != 0:
        return False

    return 'default' in result.stdout


def _check_via_ping() -> str:
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return 'fail'

    if result.returncode == 0:
        return 'inet'

    if _has_default_gateway():
        return 'local'
    return 'none'


def check_internet_status(mode: str) -> str:
    """
    Return internet connectivity status for the given check mode.

    Status values:
    - 'none': no network connection
    - 'local': local network only, no internet access
    - 'inet': full internet access
    - 'fail': the requested check command is unavailable
    """
    if mode == 'nmcli':
        return _check_via_nmcli()
    if mode == 'ping':
        return _check_via_ping()
    return 'fail'


def blink_pattern_for_internet_status(status: str) -> BlinkPattern:
    if status == 'inet':
        return BlinkPattern.from_name(options['blink_pattern_inet'])
    if status == 'local':
        return BlinkPattern.from_name(options['blink_pattern_local'])
    return BlinkPattern.from_name(options['blink_pattern_none'])


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
    # - BASE phase: keep base_brightness_pct for (period_ms - flash_2s_pulse_ms)
    # - FLASH phase: keep pulse_brightness_pct for flash_2s_pulse_ms
    base_brightness_pct = 10.0

    flash_2s_pulse_ms = 100
    inter_flash_pause_ms = 300

    pulse_brightness_by_pattern = {
        BlinkPattern.FLASH_1F_2S: 100.0,
        BlinkPattern.FLASH_2F_2S: 100.0,
        BlinkPattern.FLASH_3F_2S: 100.0,
        BlinkPattern.FLASH_4F_3S: 100.0,
        BlinkPattern.FLASH_5F_3S: 100.0,
        BlinkPattern.FLASH_10F_1S: 100.0,
        BlinkPattern.BLACK_1F_2S: 0.0,
        BlinkPattern.BLACK_2F_2S: 0.0,
        BlinkPattern.BLACK_3F_2S: 0.0,
        BlinkPattern.BLACK_4F_3S: 0.0,
        BlinkPattern.BLACK_5F_3S: 0.0,
        BlinkPattern.BLACK_10F_1S: 0.0,
    }

    flashes_by_pattern = {
        BlinkPattern.FLASH_1F_2S: 1,
        BlinkPattern.FLASH_2F_2S: 2,
        BlinkPattern.FLASH_3F_2S: 3,
        BlinkPattern.FLASH_4F_3S: 4,
        BlinkPattern.FLASH_5F_3S: 5,
        BlinkPattern.BLACK_1F_2S: 1,
        BlinkPattern.BLACK_2F_2S: 2,
        BlinkPattern.BLACK_3F_2S: 3,
        BlinkPattern.BLACK_4F_3S: 4,
        BlinkPattern.BLACK_5F_3S: 5,
    }

    three_second_patterns = {
        BlinkPattern.FLASH_4F_3S,
        BlinkPattern.FLASH_5F_3S,
        BlinkPattern.BLACK_4F_3S,
        BlinkPattern.BLACK_5F_3S,
    }

    pulse_brightness_pct = pulse_brightness_by_pattern[blink_pattern]

    if blink_pattern in flashes_by_pattern:
        period_ms = 3000 if blink_pattern in three_second_patterns else 2000
        flash_count = flashes_by_pattern[blink_pattern]
        phase_ms = t_ms % period_ms

        # One "slot" = one flash pulse + the pause that follows it.
        # The first N slots produce the flashes; the rest of the period is base.
        slot_ms = flash_2s_pulse_ms + inter_flash_pause_ms
        flashes_block_ms = slot_ms * flash_count

        if phase_ms < flashes_block_ms:
            pos_in_slot = phase_ms % slot_ms
            if pos_in_slot < flash_2s_pulse_ms:
                remaining_ms = flash_2s_pulse_ms - pos_in_slot
                return remaining_ms / 1000.0, pulse_brightness_pct
            remaining_ms = slot_ms - pos_in_slot
            return remaining_ms / 1000.0, base_brightness_pct

        remaining_ms = period_ms - phase_ms
        return remaining_ms / 1000.0, base_brightness_pct

    period_ms = 100
    flash_ms = 50
    phase_ms = t_ms % period_ms

    if phase_ms < flash_ms:
        remaining_ms = flash_ms - phase_ms
        return remaining_ms / 1000.0, pulse_brightness_pct

    remaining_ms = period_ms - phase_ms
    return remaining_ms / 1000.0, base_brightness_pct


def _update_led_and_get_pause(
    pwm: GPIO.PWM,
    blink_pattern: BlinkPattern,
    now: float,
) -> float:
    now_ms = int(now * 1000.0) % 60_000
    pause_s, brightness = compute_pause_s_and_brightness(
        blink_pattern=blink_pattern,
        t_ms=now_ms,
    )
    set_brightness(pwm, brightness)
    return pause_s


def run_shutdown_grace_blink(
    pwm: GPIO.PWM,
    *,
    seconds: float,
    loop_event: Optional[Event] = None,
) -> None:
    end_at = time.monotonic() + max(0.0, seconds)
    blink_pattern = BlinkPattern.FLASH_10F_1S

    while time.monotonic() < end_at:
        now = time.monotonic()
        pause_s = _update_led_and_get_pause(pwm, blink_pattern, now)
        if loop_event is not None:
            loop_event.wait(timeout=pause_s)
            loop_event.clear()
        else:
            time.sleep(pause_s)


def _register_shutdown_signals(
    shutdown_event: Event,
    *,
    shutdown_grace_event: Optional[Event] = None,
    loop_event: Optional[Event] = None,
) -> None:
    def handle_shutdown_signal(signum: int, frame) -> None:
        try:
            signame = signal.Signals(signum).name
        except ValueError:
            signame = str(signum)
        print(f'rpi_status_gpio stopping ({signame})')
        if signum == signal.SIGTERM and shutdown_grace_event is not None and systemd_shutdown_in_progress():
            shutdown_grace_event.set()
        shutdown_event.set()
        if loop_event is not None:
            loop_event.set()

    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)


def run_test_mode(
    pwm: GPIO.PWM,
    test_pattern: BlinkPattern,
    shutdown_event: Event,
    shutdown_grace_event: Event,
    button_state: ButtonState,
) -> None:
    print(f'rpi_status_gpio started (test mode: {test_pattern.name})')

    while not shutdown_event.is_set():
        now = time.monotonic()

        if options['button']:
            event = button_state.analyze_event(now)
            if event != ButtonEvent.NO_EVENT:
                print(event.name)

        pause_s = _update_led_and_get_pause(pwm, test_pattern, now)

        if button_state.is_button_pressed():
            # Poll frequently while the button is held so hold events are detected promptly.
            pause_s = min(pause_s, 0.5)

        loop_event.wait(timeout=pause_s)
        loop_event.clear()

    if shutdown_grace_event.is_set():
        run_shutdown_grace_blink(pwm, seconds=3.0, loop_event=loop_event)


def run_main_mode(pwm: GPIO.PWM, shutdown_event: Event, shutdown_grace_event: Event, button_state: ButtonState) -> None:
    button_action_triggered = False
    shutdown_button_event = ButtonEvent.from_name(options['button_shutdown'])
    reboot_button_event = ButtonEvent.from_name(options['button_reboot'])
    current_blink_pattern = BlinkPattern.from_name(options['blink_pattern_inet'])
    next_internet_check_at = time.monotonic() + 1.0

    print('rpi_status_gpio started')

    while not shutdown_event.is_set():
        now = time.monotonic()

        if not button_action_triggered and now >= next_internet_check_at:
            status = check_internet_status(internet_check_mode)
            print(f'Internet check ({internet_check_mode}): {status}')
            current_blink_pattern = blink_pattern_for_internet_status(status)
            if status == 'inet':
                check_interval_s = options['internet_check_interval_s']
            else:
                check_interval_s = options['internet_check_no_inet_interval_s']
            next_internet_check_at = now + check_interval_s

        if options['button']:
            event = button_state.analyze_event(now)

            if not button_action_triggered:
                if event == shutdown_button_event:
                    button_action_triggered = True
                    current_blink_pattern = BlinkPattern.FLASH_10F_1S
                    run_shutdown_command()
                elif event == reboot_button_event:
                    button_action_triggered = True
                    current_blink_pattern = BlinkPattern.FLASH_10F_1S
                    run_reboot_command()

            if event != ButtonEvent.NO_EVENT:
                print(event.name)

        pause_s = _update_led_and_get_pause(pwm, current_blink_pattern, now)

        if button_state.is_button_pressed():
            # Poll frequently while the button is held so hold events are detected promptly.
            pause_s = min(pause_s, 0.5)

        loop_event.wait(timeout=pause_s)
        loop_event.clear()

    if shutdown_grace_event.is_set():
        run_shutdown_grace_blink(pwm, seconds=3.0, loop_event=loop_event)


def parse_blink_pattern(value: str) -> BlinkPattern:
    try:
        return BlinkPattern.from_name(value)
    except KeyError:
        allowed = ', '.join(p.name for p in BlinkPattern)
        raise argparse.ArgumentTypeError(
            f'Invalid blink pattern: {value}.\nAllowed values: {allowed}.\n'
        )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Raspberry Pi status LED + shutdown button')
    parser.add_argument(
        '--test',
        type=parse_blink_pattern,
        metavar='BlinkPattern',
        help='Run the given BlinkPattern immediately',
    )
    parser.add_argument(
        '--options',
        metavar='FILE',
        help='YAML file with options overrides',
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    pwm_hz = 100

    args = parse_args(argv)

    if args.options:
        if yaml is None:
            raise ImportError('PyYAML is required when --options is used. Use: `pip install PyYAML`')

        with open(args.options, encoding='utf-8') as f:
            options.update(yaml.safe_load(f) or {})

    test_pattern: Optional[BlinkPattern] = args.test
    test_mode = test_pattern is not None

    GPIO.setmode(GPIO.BCM)
    # LED
    GPIO.setup(options['led_pin'], GPIO.OUT)
    pwm = GPIO.PWM(options['led_pin'], pwm_hz)
    pwm.start(brightness_percent_to_duty(0))

    if options['button']:
        # Button
        pull = GPIO.PUD_DOWN if options['button_is_inverted'] else GPIO.PUD_UP
        GPIO.setup(options['button_pin'], GPIO.IN, pull_up_down=pull)

    shutdown_event = Event()
    shutdown_grace_event = Event()

    loop_event.clear()
    _register_shutdown_signals(shutdown_event, shutdown_grace_event=shutdown_grace_event, loop_event=loop_event)

    button_state = ButtonState(enabled=options['button'])
    if options['button']:
        pressed = gpio_state_is_pressed(GPIO.input(options['button_pin']))
        with button_state.lock:
            button_state.button_pressed = pressed
            button_state.pressed_started_at = time.monotonic() if pressed else None
        GPIO.add_event_detect(
            options['button_pin'],
            GPIO.BOTH,
            callback=partial(button_callback, button_state),
            bouncetime=50,
        )

    try:
        if test_mode:
            run_test_mode(pwm, test_pattern, shutdown_event, shutdown_grace_event, button_state)
        else:
            run_main_mode(pwm, shutdown_event, shutdown_grace_event, button_state)
    finally:
        if options['button']:
            GPIO.remove_event_detect(options['button_pin'])
        try:
            set_brightness(pwm, 0)
            pwm.stop()
            # Without this, PWM.__del__ runs after GPIO.cleanup() and raises TypeError in lgpio
            # (chip handle is already None when the destructor calls stop() again).
            del pwm
        finally:
            GPIO.cleanup()
        print('rpi_status_gpio stopped')


if __name__ == '__main__':
    main()

