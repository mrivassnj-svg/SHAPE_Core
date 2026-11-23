"""
main.py — Raspberry Pi Pico 2 firmware for SHAPE Tier-1 node
Waveshare Pico-LCD-1.3 HAT  (240×240 ST7789, ABXY keys + joystick)

Responsibilities:
  1. Read DHT22 (temp/humidity) and MQ-135 (air quality) every 2 s
  2. Send CSV telemetry to Zero 2 W over UART (GP0/GP1, 115200 baud)
  3. Receive JSON commands from Zero 2 W (same UART)
  4. Display live sensor data + SHAPE status on the LCD
  5. ABXY navigation:
       A = toggle display mode (SENSOR ↔ STATUS)
       B = force immediate sensor read + transmit
       X = clear alert / acknowledge
       Y = show last SHAPE response (scrollable with UP/DOWN)

UART protocol (Pico → Zero 2 W):
  CSV line every 2 s:  SHAPE,{ts_ms},{temp},{humidity},{aqi},{alert}

UART protocol (Zero 2 W → Pico):
  JSON line:  {"cmd": "STATUS", "text": "Agent ready", "reward": 0.9}
              {"cmd": "ALERT",  "text": "High AQI detected"}
              {"cmd": "RESET"}
"""

import machine
import time
import json

from st7789  import ST7789, BLACK, WHITE, VIOLET, CYAN, YELLOW, GREEN, RED, ORANGE, color565
from sensors import SensorHub
from keys    import KeyHandler


# ── constants ─────────────────────────────────────────────────────────────────

SAMPLE_INTERVAL_MS = 2_000    # sensor sample period
UART_BAUD          = 115_200  # must match serial_bridge.py on Zero 2 W
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


# ── UART setup ────────────────────────────────────────────────────────────────

_uart = machine.UART(0, baudrate=UART_BAUD,
                     tx=machine.Pin(0), rx=machine.Pin(1))


# ── display modes ─────────────────────────────────────────────────────────────

MODE_SENSOR  = 0
MODE_STATUS  = 1
MODE_RESPONSE = 2


# ── helpers ───────────────────────────────────────────────────────────────────

def _send_csv(ts_ms, hub):
    """Format and transmit CSV telemetry line to Zero 2 W."""
    row = hub.csv_row(ts_ms)
    line = f"SHAPE,{row}\r\n"
    _uart.write(line.encode())


def _recv_json():
    """
    Non-blocking check for a complete JSON line from Zero 2 W.
    Returns parsed dict or None.
    """
    if _uart.any():
        try:
            raw = _uart.readline()
            if raw:
                return json.loads(raw.decode().strip())
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


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    lcd     = ST7789()
    hub     = SensorHub()
    keys    = KeyHandler()

    mode           = MODE_SENSOR
    scroll         = 0
    response_lines = []          # ring buffer of received response text
    status_text    = "Agent ready"
    reward         = None
    alert_text     = ""
    force_send     = False

    last_sample_ms  = -SAMPLE_INTERVAL_MS   # trigger immediately
    last_draw_ms    = 0
    DRAW_INTERVAL   = 250                   # redraw every 250 ms

    while True:
        now = time.ticks_ms()

        # ── key events ────────────────────────────────────────────────────
        evt = keys.poll()
        if evt == "A":
            mode = (mode + 1) % 3
            scroll = 0
        elif evt == "B":
            force_send = True
        elif evt == "X":
            alert_text = ""
        elif evt == "Y":
            mode = MODE_RESPONSE
        elif evt == "UP" and mode == MODE_RESPONSE:
            scroll = max(0, scroll - 1)
        elif evt == "DOWN" and mode == MODE_RESPONSE:
            scroll = min(max(0, len(response_lines) - 1), scroll + 1)

        # ── sensor sample ─────────────────────────────────────────────────
        if (time.ticks_diff(now, last_sample_ms) >= SAMPLE_INTERVAL_MS
                or force_send):
            hub.measure()
            _send_csv(now, hub)
            last_sample_ms = now
            force_send = False

        # ── receive from Zero 2 W ─────────────────────────────────────────
        msg = _recv_json()
        if msg:
            cmd = msg.get("cmd", "")
            if cmd == "STATUS":
                status_text = msg.get("text", "")
                reward      = msg.get("reward")
                # Add to response ring
                txt = msg.get("text", "")
                # Chunk into 39-char lines for the response screen
                while txt:
                    response_lines.append(txt[:39])
                    txt = txt[39:]
                if len(response_lines) > MAX_RESPONSE_LINES:
                    response_lines = response_lines[-MAX_RESPONSE_LINES:]
                scroll = max(0, len(response_lines) - 19)
            elif cmd == "ALERT":
                alert_text = msg.get("text", "ALERT")[:26]
            elif cmd == "RESET":
                status_text    = "Agent reset"
                reward         = None
                response_lines = []
                alert_text     = ""
                scroll         = 0

        # ── redraw ────────────────────────────────────────────────────────
        if time.ticks_diff(now, last_draw_ms) >= DRAW_INTERVAL:
            if mode == MODE_SENSOR:
                draw_sensor_screen(lcd, hub, now, alert_text)
            elif mode == MODE_STATUS:
                draw_status_screen(lcd, status_text, reward, now)
            else:
                draw_response_screen(lcd, response_lines, scroll, now)
            last_draw_ms = now

        time.sleep_ms(10)


if __name__ == "__main__":
    main()
