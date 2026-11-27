"""
pico_usb.py — Pi 5 → Pico 2 status driver over USB serial (/dev/ttyACM0)
=========================================================================

The Pico 2 is powered by the Pi 5 USB-A port.  The same USB cable carries
serial data (USB CDC ACM) — no jumper wires needed.

The Pi 5 pushes one-line JSON commands to the Pico 2 LCD at each stage of
the voice pipeline.  The Pico 2 only receives; it never sends back.

Protocol (one JSON line per command, terminated with \r\n):
  {"cmd": "LISTENING"}
  {"cmd": "THINKING"}
  {"cmd": "CONFIRMED", "text": "<first 80 chars of answer>"}
  {"cmd": "REJECTED"}
  {"cmd": "STATUS",    "text": "...", "reward": 0.9}
  {"cmd": "RESET"}

Usage:
  from hardware.pi5.pico_usb import PicoUSB
  pico = PicoUSB()          # auto-detects /dev/ttyACM0 or /dev/ttyACM1
  pico.listening()
  pico.thinking()
  pico.confirmed("Here is the answer text...")
  pico.rejected()

Group 3 — ITAI2376-14562
Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import glob as _glob
import json
import logging
import os
import threading
import time

log = logging.getLogger("shape.pico_usb")

# Default device path — override with env var PICO_USB_PORT
_DEFAULT_PORT  = os.getenv("PICO_USB_PORT", "")
_BAUD          = 115200


def _find_port() -> str:
    """Auto-detect the Pico 2 USB serial port."""
    if _DEFAULT_PORT:
        return _DEFAULT_PORT
    # Try ttyACM0 first, then ttyACM1
    for candidate in ("/dev/ttyACM0", "/dev/ttyACM1"):
        if os.path.exists(candidate):
            return candidate
    # Broader scan
    matches = _glob.glob("/dev/ttyACM*")
    if matches:
        return sorted(matches)[0]
    return ""


class PicoUSB:
    """
    Thin serial driver that pushes JSON status lines to the Pico 2 LCD.

    Thread-safe — voice_loop.py can call push() from any thread.
    Silently no-ops if the Pico 2 is not connected (showcase continues
    without the status beacon if it's unplugged).
    """

    def __init__(self, port: str = "") -> None:
        self._port   = port or _find_port()
        self._ser    = None
        self._lock   = threading.Lock()
        self._connected = False
        if self._port:
            self._connect()
        else:
            log.warning("PicoUSB: no ACM port found — Pico 2 status display disabled.")

    # ── connection ────────────────────────────────────────────────────────

    def _connect(self) -> None:
        try:
            import serial
            self._ser = serial.Serial(
                self._port, _BAUD,
                timeout=0.1,
                write_timeout=1.0,
            )
            self._connected = True
            log.info("PicoUSB: connected to Pico 2 on %s", self._port)
        except Exception as exc:
            log.warning("PicoUSB: could not open %s: %s — display disabled.", self._port, exc)
            self._connected = False

    def _reconnect(self) -> None:
        """Try once to reconnect after a write failure."""
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._connect()

    # ── low-level send ────────────────────────────────────────────────────

    def push(self, cmd: str, text: str = "", reward: float | None = None) -> None:
        """
        Send one JSON command line to the Pico 2.
        Non-blocking — silently drops if serial is unavailable.
        """
        if not self._connected:
            return
        payload: dict = {"cmd": cmd}
        if text:
            payload["text"] = text
        if reward is not None:
            payload["reward"] = round(float(reward), 3)
        line = (json.dumps(payload) + "\r\n").encode()
        with self._lock:
            try:
                self._ser.write(line)
                log.debug("PicoUSB → %s", line.strip())
            except Exception as exc:
                log.warning("PicoUSB write error: %s — attempting reconnect.", exc)
                self._connected = False
                self._reconnect()

    # ── voice pipeline helpers ────────────────────────────────────────────

    def listening(self) -> None:
        """Pi 5 mic is now recording — Pico 2 shows pulsing LISTENING screen."""
        self.push("LISTENING")

    def thinking(self) -> None:
        """Agent is processing — Pico 2 shows spinning THINKING screen."""
        self.push("THINKING")

    def confirmed(self, answer: str) -> None:
        """User confirmed on Zero 2 W — Pico 2 flashes green CONFIRMED screen."""
        self.push("CONFIRMED", text=answer[:80], reward=1.0)

    def rejected(self) -> None:
        """User rejected on Zero 2 W — Pico 2 flashes red REJECTED screen."""
        self.push("REJECTED", reward=0.0)

    def status(self, text: str, reward: float | None = None) -> None:
        """General status update — shown on the Pico 2 STATUS screen."""
        self.push("STATUS", text=text, reward=reward)

    def reset(self) -> None:
        """Clear Pico 2 display back to idle STATUS screen."""
        self.push("RESET")

    # ── context manager ───────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            if self._ser:
                try:
                    self._ser.close()
                except Exception:
                    pass
            self._connected = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
