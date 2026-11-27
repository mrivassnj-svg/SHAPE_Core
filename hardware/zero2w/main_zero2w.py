"""
Zero 2 W main application — SHAPE field terminal
=================================================
Runs on the Pi Zero 2 W. Handles:
  - Waveshare 1.3" HAT display + joystick + K1/K2/K3 keys
  - Sends user queries to Pi 5 API over Wi-Fi Direct (10.42.0.1)
  - Displays voice queries pushed from Pi 5 for K1/K3 confirm/reject
  - Caches last 10 responses for offline fallback

Controls:
  K1  = Send query / confirm
  K2  = Next page / status
  K3  = Back / cancel / reject (long-press unused — mic is on Pi 5)
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
import threading
import time
import urllib.request
import urllib.error
from collections import deque
from pathlib import Path

from hat_driver import (
    ST7789, InputHandler,
    screen_home, screen_query_input, screen_thinking,
    screen_push_query, screen_response, screen_rate, screen_status,
)

log = logging.getLogger("shape.zero2w")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PI5_URL    = os.getenv("SHAPE_PI5_URL", "http://10.42.0.1:8765")
API_KEY    = os.getenv("SHAPE_API_KEY", "shape_local_key")
CACHE_FILE = Path("/home/pi/.shape_cache.jsonl")
CACHE_SIZE = 10

# Preset query shortcuts — selected by joystick UP/DOWN from home screen
PRESETS = [
    "Write a Python function and test it",
    "Explain the ReAct reasoning loop",
    "Debug this code: print('hello' + 1)",
    "What is the SHAPE system?",
    "Write a CSV parser",
    "How do I read a file in Python?",
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
      PUSH_QUERY — Pi 5 pushed a voice query for confirmation
                   K1 = confirm (Pi 5 speaks answer aloud)
                   K2 = next page of answer
                   K3 = reject (Pi 5 discards, re-listens)
    """

    def __init__(self):
        self.lcd     = ST7789()
        self.buttons = InputHandler()
        self.client  = Pi5Client(PI5_URL, API_KEY)
        self.cache   = ResponseCache(CACHE_FILE)

        self.state        = "HOME"
        self.preset_idx   = 0
        self.current_q    = ""
        self.current_a    = ""
        self.response_pg  = 0
        self.rating       = 3
        self.pi5_online   = False

        # Voice confirmation state
        self._voice_query_id:  str  = ""
        self._voice_transcript: str = ""
        self._voice_answer:     str = ""
        self._voice_page:       int = 0

    def start(self):
        # Quick Pi 5 connectivity check
        self.pi5_online = self.client.is_online()
        log.info("Pi 5 online: %s", self.pi5_online)
        self._start_voice_poll()
        self._render()
        self._loop()

    # ── Voice poll thread ─────────────────────────────────────────────────

    def _start_voice_poll(self):
        """
        Background thread that polls /pending_voice every 1.5 s.
        When Pi 5 pushes a voice query, switches state to PUSH_QUERY so
        the user can confirm or reject it via K1 / K3.
        """
        def _poll():
            last_pending = False
            while True:
                try:
                    result = self.client._get("/pending_voice", timeout=5)
                    is_pending = result.get("pending", False)

                    if is_pending and self.state not in ("PUSH_QUERY",):
                        self._voice_query_id   = result["query_id"]
                        self._voice_transcript = result["transcript"]
                        self._voice_answer     = result["answer"]
                        self._voice_page       = 0
                        self.state = "PUSH_QUERY"
                        log.info("Voice query pushed from Pi 5: id=%s", self._voice_query_id)

                    elif not is_pending and last_pending:
                        # Cleared without us confirming — Pi 5 timeout/reset
                        if self.state == "PUSH_QUERY":
                            self.state = "HOME"

                    last_pending = is_pending
                except Exception:
                    pass
                time.sleep(1.5)

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def _send_confirm(self, confirmed: bool):
        """POST /confirm to Pi 5."""
        try:
            self.client._post("/confirm", {
                "query_id": self._voice_query_id,
                "confirmed": confirmed,
            }, timeout=10)
        except Exception as exc:
            log.warning("Confirm POST failed: %s", exc)

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
        elif self.state == "PUSH_QUERY":
            img = screen_push_query(
                self._voice_transcript,
                self._voice_answer,
                self._voice_page,
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
                    except Exception as exc:
                        log.warning("Feedback failed: %s", exc)
                    self.state = "HOME"
                elif key == "K3":  # Skip rating
                    self.state = "HOME"

            elif self.state == "STATUS":
                self.pi5_online = self.client.is_online()
                if key == "K3":
                    self.state = "HOME"

            elif self.state == "PUSH_QUERY":
                if key == "K1":    # Confirm — Pi 5 will speak the answer
                    self._send_confirm(confirmed=True)
                    self.current_a   = self._voice_answer
                    self.response_pg = 0
                    self.state       = "RESPONSE"
                elif key == "K2":  # Next page of answer
                    self._voice_page += 1
                elif key == "K3":  # Reject — Pi 5 discards and re-listens
                    self._send_confirm(confirmed=False)
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
