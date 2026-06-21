import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault('RPi', MagicMock())
sys.modules.setdefault('RPi.GPIO', MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parent))

from button_state import ButtonEvent, ButtonState


def simulate_press_release(hold_s: float) -> list[ButtonEvent]:
    t0 = 100.0
    button_state = ButtonState(enabled=True)
    events: list[ButtonEvent] = []

    button_state.update_from_gpio(True, t0)
    events.append(button_state.analyze_event(t0))

    if hold_s >= 5.0:
        events.append(button_state.analyze_event(t0 + 5.0))

    button_state.update_from_gpio(False, t0 + hold_s)
    events.append(button_state.analyze_event(t0 + hold_s))
    return events


class TestButtonState(unittest.TestCase):
    def test_disabled_returns_none(self):
        button_state = ButtonState(enabled=False)
        self.assertEqual(button_state.analyze_event(0.0), ButtonEvent.NO_EVENT)

    def test_tap_emits_pressed_then_released(self):
        events = simulate_press_release(0.5)
        self.assertEqual(events, [ButtonEvent.PRESSED, ButtonEvent.RELEASED])

    def test_hold_3s_emits_pressed_then_hold_2s(self):
        events = simulate_press_release(3.0)
        self.assertEqual(events, [ButtonEvent.PRESSED, ButtonEvent.HOLD_2S])

    def test_hold_4_5s_emits_pressed_then_released(self):
        events = simulate_press_release(4.5)
        self.assertEqual(events, [ButtonEvent.PRESSED, ButtonEvent.RELEASED])

    def test_hold_5s_emits_pressed_hold_5s_then_released(self):
        events = simulate_press_release(5.0)
        self.assertEqual(
            events,
            [ButtonEvent.PRESSED, ButtonEvent.HOLD_5S, ButtonEvent.RELEASED],
        )

    def test_hold_10s_emits_pressed_hold_5s_once_then_released(self):
        events = simulate_press_release(10.0)
        self.assertEqual(
            events,
            [ButtonEvent.PRESSED, ButtonEvent.HOLD_5S, ButtonEvent.RELEASED],
        )

    def test_hold_2s_boundary_is_hold_2s(self):
        events = simulate_press_release(2.0)
        self.assertEqual(events, [ButtonEvent.PRESSED, ButtonEvent.HOLD_2S])

    def test_hold_4s_boundary_is_hold_2s(self):
        events = simulate_press_release(4.0)
        self.assertEqual(events, [ButtonEvent.PRESSED, ButtonEvent.HOLD_2S])


if __name__ == '__main__':
    unittest.main()
