"""
Zero 2 W main application — SHAPE field terminal
=================================================
Runs on the Pi Zero 2 W. Handles:
  - Waveshare 1.3" HAT display + joystick + K1/K2/K3 keys
  - Sends user queries to Pi 5 API over Wi-Fi
  - Bridges Pico 2 serial sensor data to Pi 5
  - Caches last 10 responses for offline fallback

Controls:
  K1  = Send query / confirm
  K2  = Next page / status
  K3  = Back / cancel
  Joystick UP/DOWN = scroll menu
  Joystick LEFT/RIGHT = adjust rating

Run:  python hardware/zero2w/main_zero2w.py

Group 3 — ITAI2376-14562
Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import json
import logging
import os
import serial
import threading
import time
import urllib.request
import urllib.error
from collections import deque
from pathlib import Path

from hat_driver import (
    ST7789, InputHandler,
    screen_home, screen_query_input, screen_thinking,
    screen_response, screen_rate, screen_status,
)
from serial_bridge import SerialBridge

log = logging.getLogger("shape.zero2w")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PI5_URL     = os.getenv("SHAPE_PI5_URL", "http://192.168.4.1:8765")
API_KEY     = os.getenv("SHAPE_API_KEY", "shape_local_key")
# UART to Pico 2 (GPIO UART, not USB ACM) — override with PICO_SERIAL env var
SERIAL_PORT = os.getenv("PICO_SERIAL",   "/dev/ttyAMA1")
SERIAL_BAUD = 115200
CACHE_FILE  = Path("/home/pi/.shape_cache.jsonl")
CACHE_SIZE  = 10

# Preset query shortcuts — selected by joystick UP/DOWN from home screen
PRESETS = [
    "Show me the latest sensor readings",
    "Is the CO2 level safe?",
    "Write a function to parse the sensor CSV",
    "What should I do if CO2 exceeds 450 ppm?",
    "Explain the last anomaly detected",
    "Write a Python alert script for the sensor data",
]


# ---------------------------------------------------------------------------
# Pi 5 API client
# ---------------------------------------------------------------------------

class Pi5Client:
    def __init__(self, base_url: str, key: str):
        self.base_url = base_url.rstrip("/")
        self.key = key
        self._last_status: dict = {}

    def _headers(self) -> dict:
        return {"X-API-Key": self.key, "Content-Type": "application/json"}

    def _post(self, path: str, data: dict, timeout: int = 60) -> dict:
        url = self.base_url + path
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def _get(self, path: str, timeout: int = 5) -> dict:
        url = self.base_url + path
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def query(self, user_input: str) -> str:
        result = self._post("/query", {"input": user_input}, timeout=120)
        return result.get("output", "[No response]")

    def feedback(self, user_input: str, output: str, score: int):
        self._post("/feedback", {"input": user_input, "output": output, "score": score})

    def status(self) -> dict:
        try:
            self._last_status = self._get("/status")
        except Exception:
            pass
        return self._last_status

    def is_online(self) -> bool:
        try:
            self.status()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Response cache (offline fallback)
# ---------------------------------------------------------------------------

class ResponseCache:
    def __init__(self, path: Path, maxsize: int = CACHE_SIZE):
        self.path = path
        self.maxsize = maxsize
        self._entries: deque = deque(maxlen=maxsize)
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines()[-self.maxsize:]:
            try:
                self._entries.append(json.loads(line))
            except Exception:
                pass

    def save(self, q: str, a: str):
        entry = {"q": q, "a": a, "t": time.time()}
        self._entries.append(entry)
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def find(self, q: str) -> str | None:
        """Return cached answer for exact query match."""
        for e in reversed(self._entries):
            if e["q"].strip().lower() == q.strip().lower():
                return e["a"]
        return None

    def last(self) -> str | None:
        return self._entries[-1]["a"] if self._entries else None


# ---------------------------------------------------------------------------
# Pico 2 serial bridge (background threads via serial_bridge.SerialBridge)
# ---------------------------------------------------------------------------

class PicoReader:
    """
    Thin wrapper around SerialBridge that exposes the same .latest / .alert
    interface the rest of main_zero2w.py already uses.
    """

    def __init__(self, port: str, baud: int, pi5_base: str):
        self._bridge = SerialBridge(uart_port=port, uart_baud=baud,
                                    pi5_base=pi5_base)

    @property
    def latest(self) -> dict:
        r = self._bridge.latest_reading
        if r is None:
            return {}
        return {
            "timestamp":    r.ts_ms,
            "temp_c":       r.temperature,
            "humidity_pct": r.humidity,
            "aqi":          r.aqi,
        }

    @property
    def alert(self) -> bool:
        r = self._bridge.latest_reading
        return r.alert if r else False

    def start(self):
        ok = self._bridge.start()
        if not ok:
            log.warning("SerialBridge could not open UART — Pico 2 disconnected?")

    def stop(self):
        self._bridge.stop()

    def push_status(self, text: str, reward: float = None):
        """Forward agent status/reward back down to the Pico 2 LCD."""
        self._bridge.push_to_pico("STATUS", text, reward)


# ---------------------------------------------------------------------------
# Main UI state machine
# ---------------------------------------------------------------------------

class ShapeTerminal:
    """
    State machine for the Zero 2 W SHAPE field terminal.

    States:
      HOME       — main menu, joystick scrolls presets
      QUERY      — composing/confirming a preset query
      THINKING   — waiting for Pi 5 response
      RESPONSE   — displaying paginated response
      RATE       — rating the response (RL feedback)
      STATUS     — system status screen
    """

    def __init__(self):
        self.lcd     = ST7789()
        self.buttons = InputHandler()
        self.client  = Pi5Client(PI5_URL, API_KEY)
        self.cache   = ResponseCache(CACHE_FILE)
        self.pico    = PicoReader(SERIAL_PORT, SERIAL_BAUD, PI5_URL)

        self.state        = "HOME"
        self.preset_idx   = 0
        self.current_q    = ""
        self.current_a    = ""
        self.response_pg  = 0
        self.rating       = 3
        self.pi5_online   = False

    def start(self):
        self.pico.start()
        # Quick Pi 5 connectivity check
        self.pi5_online = self.client.is_online()
        log.info("Pi 5 online: %s", self.pi5_online)
        self._render()
        self._loop()

    def _render(self):
        """Draw current state to LCD."""
        if self.state == "HOME":
            img = screen_home()
        elif self.state == "QUERY":
            img = screen_query_input(self.current_q)
        elif self.state == "THINKING":
            img = screen_thinking()
        elif self.state == "RESPONSE":
            img = screen_response(self.current_a, self.response_pg)
        elif self.state == "RATE":
            img = screen_rate(self.rating)
        elif self.state == "STATUS":
            st = self.client.status()
            img = screen_status(
                st.get("model", "unknown"),
                st.get("rl", {}).get("avg_score"),
                st.get("rl", {}).get("records", 0),
            )
        else:
            img = screen_home()
        self.lcd.show(img)

    def _ask_pi5(self, query: str) -> str:
        """Send query to Pi 5; fall back to cache if offline."""
        if not self.pi5_online:
            cached = self.cache.find(query)
            if cached:
                return f"[Cached] {cached}"
            return "[Offline] Pi 5 unreachable. No cached answer for this query."
        try:
            answer = self.client.query(query)
            self.cache.save(query, answer)
            return answer
        except Exception as exc:
            log.error("Pi 5 query failed: %s", exc)
            cached = self.cache.find(query)
            return f"[Fallback] {cached}" if cached else f"[Error] {exc}"

    def _loop(self):
        """Main event loop — polls buttons and updates state."""
        while True:
            key = self.buttons.wait_for_press(timeout=0.05)

            if self.state == "HOME":
                if key == "UP":
                    self.preset_idx = (self.preset_idx - 1) % len(PRESETS)
                    self.current_q  = PRESETS[self.preset_idx]
                elif key == "DOWN":
                    self.preset_idx = (self.preset_idx + 1) % len(PRESETS)
                    self.current_q  = PRESETS[self.preset_idx]
                elif key == "K1":
                    if not self.current_q:
                        self.current_q = PRESETS[0]
                    self.state = "QUERY"
                elif key == "K2":
                    self.state = "STATUS"
                elif key == "PRESS":
                    # Joystick press = quick send with selected preset
                    if not self.current_q:
                        self.current_q = PRESETS[self.preset_idx]
                    self.state = "THINKING"
                    self._render()
                    self.current_a   = self._ask_pi5(self.current_q)
                    self.response_pg = 0
                    self.state = "RESPONSE"

            elif self.state == "QUERY":
                if key == "K1":    # Send
                    self.state = "THINKING"
                    self._render()
                    self.current_a   = self._ask_pi5(self.current_q)
                    self.response_pg = 0
                    self.state = "RESPONSE"
                elif key == "K2":  # Clear query
                    self.current_q = ""
                elif key == "K3":  # Back
                    self.state = "HOME"

            elif self.state == "RESPONSE":
                if key == "K1":    # Rate
                    self.rating = 3
                    self.state  = "RATE"
                elif key == "K2":  # Next page
                    self.response_pg += 1
                elif key == "K3":  # Home
                    self.state = "HOME"

            elif self.state == "RATE":
                if key == "LEFT":
                    self.rating = max(1, self.rating - 1)
                elif key == "RIGHT":
                    self.rating = min(5, self.rating + 1)
                elif key in ("PRESS", "K1"):   # Confirm
                    try:
                        self.client.feedback(
                            self.current_q, self.current_a, self.rating)
                        log.info("Feedback sent: %d", self.rating)
                        # Mirror the reward back to the Pico 2 LCD
                        self.pico.push_status(
                            self.current_a[:40],
                            round(self.rating / 5.0, 2),
                        )
                    except Exception as exc:
                        log.warning("Feedback failed: %s", exc)
                    self.state = "HOME"
                elif key == "K3":  # Skip rating
                    self.state = "HOME"

            elif self.state == "STATUS":
                self.pi5_online = self.client.is_online()
                if key == "K3":
                    self.state = "HOME"

            self._render()
            time.sleep(0.03)   # ~30 fps poll rate


if __name__ == "__main__":
    terminal = ShapeTerminal()
    try:
        terminal.start()
    except KeyboardInterrupt:
        terminal.lcd.cleanup()
        log.info("SHAPE Zero 2 W terminal stopped.")
