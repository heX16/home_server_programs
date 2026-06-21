from dataclasses import dataclass, field
from enum import Enum, auto
from threading import Lock
from typing import Optional


class ButtonEvent(Enum):
    NOT_DEFINED = auto()
    NO_EVENT = auto()
    PRESSED = auto()
    RELEASED = auto()
    RELEASED_HOLD_2S = auto()
    HOLD_5S = auto()

    @classmethod
    def from_name(cls, value: str) -> 'ButtonEvent':
        if value.lower() in ('none', ''):
            return cls.NOT_DEFINED
        return cls[value.upper()]


@dataclass
class ButtonState:
    enabled: bool
    lock: Lock = field(default_factory=Lock)
    button_pressed: bool = False
    pressed_started_at: Optional[float] = None
    prev_button_pressed: bool = False
    hold_emitted: bool = False
    button_pressed_now: bool = False
    last_released_hold_s: Optional[float] = None

    def update_from_gpio(self, pressed_now: bool, ts: float) -> None:
        with self.lock:
            if pressed_now and not self.button_pressed:
                self.button_pressed = True
                self.pressed_started_at = ts
            elif not pressed_now and self.button_pressed:
                if self.pressed_started_at is not None:
                    self.last_released_hold_s = ts - self.pressed_started_at
                self.button_pressed = False
                self.pressed_started_at = None

    def is_button_pressed(self) -> bool:
        with self.lock:
            return self.button_pressed

    def analyze_event(self, now: float) -> ButtonEvent:
        """
        Analyze button press/release/hold and return one event for this loop iteration.

        Returns ButtonEvent.NO_EVENT when enabled is False.
        """
        if not self.enabled:
            return ButtonEvent.NO_EVENT

        hold_2s_lo = 2.0
        hold_2s_hi = 4.0
        hold_5s = 5.0

        with self.lock:
            hold_started_at = self.pressed_started_at
            button_pressed_now = hold_started_at is not None
            prev = self.prev_button_pressed
            event = ButtonEvent.NO_EVENT

            if (
                button_pressed_now
                and hold_started_at is not None
                and (now - hold_started_at) >= hold_5s
                and not self.hold_emitted
            ):
                event = ButtonEvent.HOLD_5S
                self.hold_emitted = True
            elif button_pressed_now and not prev:
                event = ButtonEvent.PRESSED
            elif not button_pressed_now and prev:
                released_hold_s = self.last_released_hold_s
                self.last_released_hold_s = None
                if (
                    released_hold_s is not None
                    and hold_2s_lo <= released_hold_s <= hold_2s_hi
                ):
                    event = ButtonEvent.RELEASED_HOLD_2S
                else:
                    event = ButtonEvent.RELEASED
                self.hold_emitted = False

            self.prev_button_pressed = button_pressed_now
            self.button_pressed_now = button_pressed_now
            return event
