"""
keys.py — ABXY + joystick button handler for Waveshare Pico-LCD-1.3 HAT
Runs on Raspberry Pi Pico 2 (MicroPython).

GPIO mapping (from Waveshare schematic):
  Joystick: UP=GP2  DOWN=GP18  LEFT=GP16  RIGHT=GP20  PRESS=GP3
  Keys:      A=GP15  B=GP17     X=GP19     Y=GP21

All inputs use internal pull-ups; buttons are active-LOW.
"""

import machine
import time


# ── pin map ───────────────────────────────────────────────────────────────────

_PIN_MAP = {
    "UP":    2,
    "DOWN":  18,
    "LEFT":  16,
    "RIGHT": 20,
    "PRESS": 3,
    "A":     15,
    "B":     17,
    "X":     19,
    "Y":     21,
}

# How long (ms) to debounce press events
_DEBOUNCE_MS = 50


class KeyHandler:
    """
    Non-blocking button poller with debounce.

    Usage in a main loop:
        keys = KeyHandler()
        while True:
            evt = keys.poll()
            if evt:
                print("pressed:", evt)
    """

    def __init__(self):
        self._pins = {
            name: machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)
            for name, pin in _PIN_MAP.items()
        }
        # Track last stable state to detect edges
        self._last_state  = {name: 1 for name in _PIN_MAP}   # 1 = released
        self._last_change = {name: 0 for name in _PIN_MAP}   # ms timestamp

    def poll(self):
        """
        Check all buttons for a fresh press event.
        Returns the button name string on a confirmed press, None otherwise.
        One event per call; call every ~10 ms in the main loop.
        """
        now = time.ticks_ms()
        for name, pin in self._pins.items():
            val = pin.value()
            if val != self._last_state[name]:
                self._last_change[name] = now
                self._last_state[name]  = val
            elif (val == 0
                  and time.ticks_diff(now, self._last_change[name]) >= _DEBOUNCE_MS
                  and self._last_change[name] != 0):
                # Confirmed press after debounce window; arm re-trigger only on release
                self._last_change[name] = 0
                return name
        return None

    def is_pressed(self, name: str) -> bool:
        """Instant (non-debounced) read; True when button is currently held."""
        return self._pins[name].value() == 0

    def any_pressed(self) -> bool:
        """True if any button is currently held."""
        return any(p.value() == 0 for p in self._pins.values())
