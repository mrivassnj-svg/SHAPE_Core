"""
main.py — Raspberry Pi Pico 2 firmware for SHAPE Tier-1 node
Waveshare Pico-LCD-1.3 HAT  (240×240 ST7789, ABXY keys + joystick)

Responsibilities:
  1. Acts as the visual status beacon for the SHAPE voice showcase rig.
  2. Receive JSON commands from Pi 5 over USB CDC serial (USB cable, /dev/ttyACM0)
  3. Display agent status + voice pipeline state on the LCD
  4. ABXY navigation:
       A = toggle display mode (STATUS / RESPONSE)
       X = clear alert / acknowledge
       Y = show last SHAPE response (scrollable with UP/DOWN)

USB CDC protocol (Pi 5 -> Pico 2, one JSON line per message):
  {"cmd": "STATUS",    "text": "Agent ready",    "reward": 0.9}
  {"cmd": "ALERT",     "text": "High AQI ..."}
  {"cmd": "LISTENING"}                   <- Pi 5 mic is recording
  {"cmd": "THINKING"}                    <- agent.run() in progress
  {"cmd": "CONFIRMED", "text": "answer"} <- user confirmed on Zero 2 W
  {"cmd": "REJECTED"}                    <- user rejected on Zero 2 W
  {"cmd": "RESET"}
"""

import sys
import time
import json

from st7789 import ST7789, BLACK, WHITE, VIOLET, CYAN, YELLOW, GREEN, RED, ORANGE, color565
from keys   import KeyHandler


# ── constants ─────────────────────────────────────────────────────────────────

MAX_RESPONSE_LINES = 20       # ring buffer for SHAPE responses

# Display colour palette (matches SHAPE anime palette)
BG        = VIOLET
HEADER_BG = color565(30, 0, 60)
BORDER    = CYAN
TEXT_COL  = WHITE
DIM_COL   = color565(130, 130, 180)
OK_COL    = GREEN
WARN_COL  = YELLOW
ERR_COL   = RED


# ── USB CDC input buffer ───────────────────────────────────────────────────────

_usb_buf = b""   # accumulate bytes until a newline arrives


# ── display modes ─────────────────────────────────────────────────────────────

MODE_STATUS    = 0   # agent status + reward bar  (default)
MODE_RESPONSE  = 1   # scrollable last answer
MODE_LISTENING = 2   # Pi 5 mic is recording
MODE_THINKING  = 3   # agent.run() in progress
MODE_CONFIRMED = 4   # answer accepted — flash green
MODE_REJECTED  = 5   # answer rejected — flash red


# ── helpers ───────────────────────────────────────────────────────────────────

def _recv_json():
    """
    Non-blocking check for a complete JSON line from Pi 5 via USB CDC.
    Accumulates bytes in _usb_buf until a newline is found.
    Returns parsed dict or None.
    """
    global _usb_buf
    # sys.stdin.buffer is the raw USB CDC byte stream in MicroPython
    chunk = sys.stdin.buffer.read(64) if hasattr(sys.stdin, 'buffer') else b""
    if chunk:
        _usb_buf += chunk
    if b"\n" in _usb_buf:
        line, _usb_buf = _usb_buf.split(b"\n", 1)
        try:
            return json.loads(line.decode().strip())
        except (ValueError, UnicodeError):
            pass
    return None


def _aqi_color(aqi):
    if aqi is None:    return DIM_COL
    if aqi < 200:      return OK_COL
    if aqi < 500:      return WARN_COL
    return ERR_COL


def _temp_color(t):
    if t is None:   return DIM_COL
    if t < 30:      return OK_COL
    if t < 38:      return WARN_COL
    return ERR_COL


# ── screen drawing ────────────────────────────────────────────────────────────

def draw_header(lcd, title, ts_ms):
    lcd.rect(0, 0, 240, 20, HEADER_BG)
    lcd.hline(0, 20, 240, BORDER)
    lcd.text_center(4, title[:26], CYAN, HEADER_BG, scale=1)
    # Uptime in seconds (top-right, tiny)
    secs = ts_ms // 1000
    lcd.text(190, 4, f"{secs}s", DIM_COL, HEADER_BG)


def draw_sensor_screen(lcd, hub, ts_ms, alert_text):
    """Full sensor dashboard."""
    lcd.fill(BG)
    draw_header(lcd, "SHAPE SENSOR NODE", ts_ms)

    y = 28

    # Temperature
    t  = hub.temperature
    tc = _temp_color(t)
    tv = f"{t:.1f}C" if t is not None else "---"
    lcd.text(8,  y, "TEMP", DIM_COL, BG)
    lcd.text_center(y, tv, tc, BG, scale=2)
    y += 20

    # Humidity
    h  = hub.humidity
    hv = f"{h:.1f}%" if h is not None else "---"
    lcd.text(8,  y, "RH  ", DIM_COL, BG)
    lcd.text_center(y, hv, TEXT_COL, BG, scale=2)
    y += 20

    # AQI bar
    aq  = hub.aqi
    aqc = _aqi_color(aq)
    aqv = f"{aq:.0f}" if aq is not None else "---"
    lcd.text(8,  y, "AQI ", DIM_COL, BG)
    lcd.text_center(y, aqv, aqc, BG, scale=2)
    y += 20

    # AQI bar (visual)
    bar_w = int((aq or 0) / 1000 * 220)
    bar_w = min(bar_w, 220)
    lcd.hline(10, y, 220, DIM_COL)
    if bar_w > 0:
        lcd.rect(10, y - 4, bar_w, 8, aqc)
    y += 16

    lcd.hline(0, y, 240, BORDER); y += 4

    # Alert
    if hub.air_alert:
        lcd.text_center(y, "!! AIR ALERT !!", ERR_COL, BG, scale=1)
        y += 10
    if not hub.is_healthy:
        lcd.text_center(y, "DHT ERR x" + str(hub.consecutive_errors), ERR_COL, BG, scale=1)
        y += 10

    if alert_text:
        lcd.text_center(y, alert_text[:26], WARN_COL, BG, scale=1)
        y += 10

    # Key hints at bottom
    lcd.hline(0, 228, 240, BORDER)
    lcd.text(4,   231, "A:MODE", DIM_COL, BG)
    lcd.text(90,  231, "B:SEND", DIM_COL, BG)
    lcd.text(170, 231, "X:CLR",  DIM_COL, BG)


def draw_status_screen(lcd, status_text, reward, ts_ms):
    """Agent status page."""
    lcd.fill(BG)
    draw_header(lcd, "SHAPE AGENT STATUS", ts_ms)

    y = 28
    lcd.text_center(y, "AGENT", DIM_COL, BG); y += 12
    agent_state = status_text or "Waiting..."
    # Word-wrap crude: 26 chars per line
    words = agent_state.split()
    line = ""
    for w in words:
        if len(line) + len(w) + 1 > 26:
            lcd.text(4, y, line, TEXT_COL, BG); y += 10; line = w
        else:
            line = (line + " " + w).strip()
    if line:
        lcd.text(4, y, line, TEXT_COL, BG); y += 10

    y += 4; lcd.hline(0, y, 240, BORDER); y += 6

    if reward is not None:
        rw = int(reward * 220)
        lcd.text(8, y, f"REWARD {reward:.2f}", OK_COL if reward >= 0.5 else WARN_COL, BG)
        y += 10
        lcd.rect(10, y, rw, 6, OK_COL if reward >= 0.5 else WARN_COL)
        y += 12

    lcd.hline(0, 228, 240, BORDER)
    lcd.text(4,   231, "A:MODE", DIM_COL, BG)
    lcd.text(90,  231, "Y:RESP", DIM_COL, BG)


def draw_response_screen(lcd, lines, scroll, ts_ms):
    """Scrollable SHAPE response viewer."""
    lcd.fill(BG)
    draw_header(lcd, "SHAPE RESPONSE", ts_ms)

    y = 24
    max_visible = 19
    shown = lines[scroll: scroll + max_visible]
    for ln in shown:
        lcd.text(2, y, ln[:39], TEXT_COL, BG); y += 10

    lcd.hline(0, 228, 240, BORDER)
    lcd.text(4,   231, "A:MODE",  DIM_COL, BG)
    lcd.text(85,  231, "UP/DN",   DIM_COL, BG)
    lcd.text(165, 231, "Y:BACK",  DIM_COL, BG)


def draw_listening_screen(lcd, ts_ms):
    """Pulsing 'LISTENING' screen — shown while Pi 5 mic is recording."""
    lcd.fill(BG)
    draw_header(lcd, "SHAPE VOICE", ts_ms)
    # Animated dot: 3 dots cycling with ts_ms
    dots = "." * ((ts_ms // 500) % 4)
    lcd.text_center(80,  "LISTENING",  CYAN, BG, scale=2)
    lcd.text_center(118, dots,         CYAN, BG, scale=2)
    lcd.text_center(145, "Speak now", DIM_COL, BG, scale=1)
    lcd.hline(0, 228, 240, BORDER)
    lcd.text(4, 231, "X:Cancel", DIM_COL, BG)


def draw_thinking_screen(lcd, ts_ms):
    """Shown while Pi 5 agent.run() is in progress."""
    lcd.fill(BG)
    draw_header(lcd, "SHAPE THINKING", ts_ms)
    spin = ["|", "/", "-", "\\"][(ts_ms // 300) % 4]
    lcd.text_center(80,  "THINKING",   YELLOW, BG, scale=2)
    lcd.text_center(118, spin,         YELLOW, BG, scale=2)
    lcd.text_center(145, "CodeLlama", DIM_COL, BG, scale=1)
    lcd.hline(0, 228, 240, BORDER)


def draw_confirmed_screen(lcd, text, ts_ms):
    """Flash green — answer confirmed by user on Zero 2 W."""
    lcd.fill(color565(0, 40, 10))
    draw_header(lcd, "CONFIRMED", ts_ms)
    lcd.text_center(70,  "OK",        GREEN, color565(0, 40, 10), scale=3)
    lcd.text_center(118, "Speaking!", GREEN, color565(0, 40, 10), scale=1)
    # Show first 26 chars of answer
    if text:
        lcd.text(4, 148, text[:26],  WHITE, color565(0, 40, 10))
        if len(text) > 26:
            lcd.text(4, 162, text[26:52], WHITE, color565(0, 40, 10))
    lcd.hline(0, 228, 240, BORDER)


def draw_rejected_screen(lcd, ts_ms):
    """Flash red — answer rejected by user on Zero 2 W."""
    lcd.fill(color565(40, 0, 0))
    draw_header(lcd, "REJECTED", ts_ms)
    lcd.text_center(80,  "RETRY",    RED, color565(40, 0, 0), scale=2)
    lcd.text_center(115, "Listening again...", DIM_COL, color565(40, 0, 0), scale=1)
    lcd.hline(0, 228, 240, BORDER)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    lcd  = ST7789()
    keys = KeyHandler()

    mode           = MODE_STATUS
    scroll         = 0
    response_lines = []          # ring buffer of received response text
    status_text    = "Agent ready"
    reward         = None
    alert_text     = ""
    confirmed_text = ""

    # Transient mode timeout: LISTENING/THINKING/CONFIRMED/REJECTED auto-revert
    # to STATUS after this many ms if no further command arrives.
    TRANSIENT_MS  = 4000
    transient_at  = 0            # ticks_ms when transient mode was entered

    last_draw_ms  = 0
    DRAW_INTERVAL = 250          # redraw every 250 ms

    while True:
        now = time.ticks_ms()

        # ── key events ────────────────────────────────────────────────────
        evt = keys.poll()
        if evt == "A":
            # Cycle between STATUS and RESPONSE only
            if mode in (MODE_STATUS, MODE_RESPONSE):
                mode = MODE_RESPONSE if mode == MODE_STATUS else MODE_STATUS
                scroll = 0
        elif evt == "X":
            alert_text = ""
            if mode not in (MODE_STATUS, MODE_RESPONSE):
                mode = MODE_STATUS  # cancel any transient state
        elif evt == "Y":
            mode   = MODE_RESPONSE
            scroll = 0
        elif evt == "UP" and mode == MODE_RESPONSE:
            scroll = max(0, scroll - 1)
        elif evt == "DOWN" and mode == MODE_RESPONSE:
            scroll = min(max(0, len(response_lines) - 1), scroll + 1)

        # ── receive from Pi 5 via USB CDC ────────────────────────────────
        msg = _recv_json()
        if msg:
            cmd = msg.get("cmd", "")

            if cmd == "STATUS":
                status_text = msg.get("text", "")
                reward      = msg.get("reward")
                # Accumulate answer text in response ring
                txt = msg.get("text", "")
                while txt:
                    response_lines.append(txt[:39])
                    txt = txt[39:]
                if len(response_lines) > MAX_RESPONSE_LINES:
                    response_lines = response_lines[-MAX_RESPONSE_LINES:]
                scroll = max(0, len(response_lines) - 19)
                if mode not in (MODE_STATUS, MODE_RESPONSE):
                    mode = MODE_STATUS

            elif cmd == "ALERT":
                alert_text = msg.get("text", "ALERT")[:26]

            elif cmd == "LISTENING":
                mode        = MODE_LISTENING
                transient_at = now

            elif cmd == "THINKING":
                mode        = MODE_THINKING
                transient_at = now

            elif cmd == "CONFIRMED":
                confirmed_text = msg.get("text", "")
                # Chunk confirmed answer into response ring
                txt = confirmed_text
                while txt:
                    response_lines.append(txt[:39])
                    txt = txt[39:]
                if len(response_lines) > MAX_RESPONSE_LINES:
                    response_lines = response_lines[-MAX_RESPONSE_LINES:]
                scroll = max(0, len(response_lines) - 19)
                mode        = MODE_CONFIRMED
                transient_at = now

            elif cmd == "REJECTED":
                mode        = MODE_REJECTED
                transient_at = now

            elif cmd == "RESET":
                status_text    = "Agent reset"
                reward         = None
                response_lines = []
                alert_text     = ""
                confirmed_text = ""
                scroll         = 0
                mode           = MODE_STATUS

        # ── auto-revert transient modes after TRANSIENT_MS ────────────────
        if mode in (MODE_LISTENING, MODE_THINKING, MODE_CONFIRMED, MODE_REJECTED):
            if time.ticks_diff(now, transient_at) > TRANSIENT_MS:
                mode = MODE_STATUS

        # ── redraw ────────────────────────────────────────────────────────
        if time.ticks_diff(now, last_draw_ms) >= DRAW_INTERVAL:
            if mode == MODE_STATUS:
                draw_status_screen(lcd, status_text, reward, now)
            elif mode == MODE_RESPONSE:
                draw_response_screen(lcd, response_lines, scroll, now)
            elif mode == MODE_LISTENING:
                draw_listening_screen(lcd, now)
            elif mode == MODE_THINKING:
                draw_thinking_screen(lcd, now)
            elif mode == MODE_CONFIRMED:
                draw_confirmed_screen(lcd, confirmed_text, now)
            elif mode == MODE_REJECTED:
                draw_rejected_screen(lcd, now)
            last_draw_ms = now

        time.sleep_ms(10)


if __name__ == "__main__":
    main()
