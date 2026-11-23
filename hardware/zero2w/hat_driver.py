"""
Waveshare 1.3" LCD HAT driver for Raspberry Pi Zero 2 W
========================================================
Hardware layout (looking at the HAT from above):

  ┌─────────────────────────────────────┐
  │  [JOY]           [LCD 240×240]   [K1]│
  │  UP/DN/LT/RT/PR                  [K2]│
  │                                  [K3]│
  └─────────────────────────────────────┘

GPIO pin map (BCM numbering):
  Joystick UP    = 6    (active LOW, internal pull-up)
  Joystick DOWN  = 19
  Joystick LEFT  = 5
  Joystick RIGHT = 26
  Joystick PRESS = 13
  Key K1         = 21
  Key K2         = 20
  Key K3         = 16

LCD (ST7789, SPI0):
  SCLK  = GPIO 11 (SPI0_CLK)
  MOSI  = GPIO 10 (SPI0_MOSI)
  CS    = GPIO 8  (SPI0_CE0)
  DC    = GPIO 25
  RST   = GPIO 27
  BL    = GPIO 24  (backlight PWM)

Dependencies:
    pip install RPi.GPIO spidev Pillow

Group 3 — ITAI2376-14562
Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import time
from typing import Callable

try:
    import RPi.GPIO as GPIO
    import spidev
    _HW = True
except ImportError:
    # Allow import on non-Pi machines (CI / simulation)
    _HW = False

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Pin definitions
# ---------------------------------------------------------------------------
PIN_JOY_UP    =  6
PIN_JOY_DOWN  = 19
PIN_JOY_LEFT  =  5
PIN_JOY_RIGHT = 26
PIN_JOY_PRESS = 13
PIN_K1        = 21
PIN_K2        = 20
PIN_K3        = 16

PIN_LCD_DC    = 25
PIN_LCD_RST   = 27
PIN_LCD_BL    = 24

LCD_W = 240
LCD_H = 240

# ---------------------------------------------------------------------------
# LCD driver (ST7789)
# ---------------------------------------------------------------------------

class ST7789:
    """Minimal ST7789 driver over SPI for the Waveshare 1.3" HAT."""

    def __init__(self):
        if not _HW:
            self._sim = True
            return
        self._sim = False
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in (PIN_LCD_DC, PIN_LCD_RST, PIN_LCD_BL):
            GPIO.setup(pin, GPIO.OUT)
        GPIO.output(PIN_LCD_BL, GPIO.HIGH)   # backlight on

        self._spi = spidev.SpiDev()
        self._spi.open(0, 0)
        self._spi.max_speed_hz = 40_000_000
        self._spi.mode = 0b11

        self._reset()
        self._init_display()

    def _reset(self):
        GPIO.output(PIN_LCD_RST, GPIO.HIGH); time.sleep(0.01)
        GPIO.output(PIN_LCD_RST, GPIO.LOW);  time.sleep(0.01)
        GPIO.output(PIN_LCD_RST, GPIO.HIGH); time.sleep(0.05)

    def _cmd(self, cmd: int, *data: int):
        GPIO.output(PIN_LCD_DC, GPIO.LOW)
        self._spi.writebytes([cmd])
        if data:
            GPIO.output(PIN_LCD_DC, GPIO.HIGH)
            self._spi.writebytes(list(data))

    def _init_display(self):
        # ST7789 240×240 initialisation sequence
        self._cmd(0x36, 0x70)   # MADCTL: row/col order
        self._cmd(0x3A, 0x05)   # COLMOD: 16-bit color
        self._cmd(0xB2, 0x0C, 0x0C, 0x00, 0x33, 0x33)
        self._cmd(0xB7, 0x35)
        self._cmd(0xBB, 0x19)
        self._cmd(0xC0, 0x2C)
        self._cmd(0xC2, 0x01)
        self._cmd(0xC3, 0x12)
        self._cmd(0xC4, 0x20)
        self._cmd(0xC6, 0x0F)
        self._cmd(0xD0, 0xA4, 0xA1)
        self._cmd(0x11)   # Sleep out
        time.sleep(0.12)
        self._cmd(0x29)   # Display on

    def show(self, img: Image.Image):
        """Push a 240×240 RGB PIL image to the display."""
        if self._sim:
            img.save("/tmp/shape_zero_display.png")
            return
        img = img.convert("RGB").resize((LCD_W, LCD_H))
        # Set column/row address
        self._cmd(0x2A, 0x00, 0x00, 0x00, 0xEF)
        self._cmd(0x2B, 0x00, 0x00, 0x00, 0xEF)
        self._cmd(0x2C)
        GPIO.output(PIN_LCD_DC, GPIO.HIGH)
        # Convert to 16-bit (RGB565) and send in chunks
        pixels = img.tobytes()
        rgb565 = bytearray(LCD_W * LCD_H * 2)
        for i in range(LCD_W * LCD_H):
            r, g, b = pixels[i*3], pixels[i*3+1], pixels[i*3+2]
            c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            rgb565[i*2]   = (c >> 8) & 0xFF
            rgb565[i*2+1] = c & 0xFF
        # SpiDev max transfer = 4096 bytes
        chunk = 4096
        for start in range(0, len(rgb565), chunk):
            self._spi.writebytes(list(rgb565[start:start+chunk]))

    def cleanup(self):
        if not self._sim:
            GPIO.output(PIN_LCD_BL, GPIO.LOW)
            self._spi.close()
            GPIO.cleanup()


# ---------------------------------------------------------------------------
# Button / joystick reader
# ---------------------------------------------------------------------------

class InputHandler:
    """
    Polls GPIO inputs for the Zero 2 W HAT.
    All inputs are active-LOW with internal pull-ups.

    Layout:
      Left side  — joystick (UP/DOWN/LEFT/RIGHT/PRESS)
      Right side — K1 (top), K2 (middle), K3 (bottom)
    """

    PINS = {
        "UP":    PIN_JOY_UP,
        "DOWN":  PIN_JOY_DOWN,
        "LEFT":  PIN_JOY_LEFT,
        "RIGHT": PIN_JOY_RIGHT,
        "PRESS": PIN_JOY_PRESS,
        "K1":    PIN_K1,
        "K2":    PIN_K2,
        "K3":    PIN_K3,
    }

    def __init__(self):
        if not _HW:
            self._sim = True
            return
        self._sim = False
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in self.PINS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def pressed(self, name: str) -> bool:
        """Return True if the named button/direction is currently pressed."""
        if self._sim:
            return False
        pin = self.PINS[name]
        return GPIO.input(pin) == GPIO.LOW

    def any_pressed(self) -> str | None:
        """Return the name of the first pressed input, or None."""
        for name in self.PINS:
            if self.pressed(name):
                return name
        return None

    def wait_for_press(self, timeout: float = 30.0) -> str | None:
        """Block until any button is pressed or timeout expires."""
        start = time.time()
        while time.time() - start < timeout:
            key = self.any_pressed()
            if key:
                time.sleep(0.05)   # debounce
                return key
            time.sleep(0.02)
        return None


# ---------------------------------------------------------------------------
# UI renderer — draws SHAPE screens onto a 240×240 PIL canvas
# ---------------------------------------------------------------------------

BG      = (10,  8, 26)
BLUE    = (25, 140, 255)
GRN     = (20, 255, 115)
YEL     = (255, 224, 0)
WHT     = (255, 255, 255)
GRY     = (140, 140, 160)
TEAL    = (0, 230, 220)
RED     = (255, 40, 40)
ORG     = (255, 115, 0)
INK     = (5, 5, 10)
PINK    = (255, 46, 140)

def _font(size=14, bold=False):
    path = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def screen_home() -> Image.Image:
    """Main menu screen."""
    img = Image.new("RGB", (240, 240), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([4, 4, 235, 235], outline=BLUE, width=2)
    d.text((120, 28),  "SHAPE",    font=_font(32, True), fill=YEL, anchor="mm")
    d.text((120, 60),  "v1.0",     font=_font(14),       fill=TEAL, anchor="mm")
    d.line([(20, 72), (220, 72)], fill=BLUE, width=1)
    items = [
        ("K1  Ask SHAPE",      WHT),
        ("K2  Status",         GRY),
        ("K3  Settings",       GRY),
        ("",                   GRY),
        ("JOY Navigate",       GRY),
        ("PRE Select",         GRY),
    ]
    for i, (txt, col) in enumerate(items):
        d.text((20, 88 + i * 24), txt, font=_font(15), fill=col)
    return img


def screen_query_input(prompt: str, cursor: bool = True) -> Image.Image:
    """Input prompt screen — user is composing a query via joystick."""
    img = Image.new("RGB", (240, 240), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, 240, 28], fill=BLUE)
    d.text((120, 14), "Ask SHAPE", font=_font(14, True), fill=INK, anchor="mm")
    d.rectangle([4, 32, 235, 180], outline=GRN, width=1)
    # Word-wrap the prompt at ~26 chars
    words = prompt.split()
    lines, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > 26:
            lines.append(line); line = w
        else:
            line = (line + " " + w).strip()
    if line:
        lines.append(line)
    if cursor:
        lines.append("▌")
    for i, l in enumerate(lines[-6:]):
        d.text((10, 42 + i * 22), l, font=_font(14), fill=WHT)
    d.text((10, 192), "K1 Send  K2 Clear  K3 Back", font=_font(12), fill=GRY)
    return img


def screen_thinking() -> Image.Image:
    """Shown while waiting for Pi 5 to respond."""
    img = Image.new("RGB", (240, 240), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([4, 4, 235, 235], outline=TEAL, width=2)
    d.text((120, 90),  "SHAPE",         font=_font(26, True), fill=YEL,  anchor="mm")
    d.text((120, 125), "Thinking…",     font=_font(20),       fill=TEAL, anchor="mm")
    d.text((120, 158), "CodeLlama 13B", font=_font(13),       fill=GRY,  anchor="mm")
    d.text((120, 178), "Offline · Pi 5",font=_font(13),       fill=GRY,  anchor="mm")
    return img


def screen_response(text: str, page: int = 0) -> Image.Image:
    """Display a paginated agent response."""
    img = Image.new("RGB", (240, 240), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, 240, 24], fill=BLUE)
    d.text((120, 12), "SHAPE Answer", font=_font(13, True), fill=INK, anchor="mm")
    # Word-wrap at 26 chars
    words = text.split()
    lines, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > 26:
            lines.append(line); line = w
        else:
            line = (line + " " + w).strip()
    if line:
        lines.append(line)
    per_page = 7
    start    = page * per_page
    shown    = lines[start:start + per_page]
    for i, l in enumerate(shown):
        d.text((6, 32 + i * 27), l, font=_font(14), fill=WHT)
    total_pages = max(1, (len(lines) + per_page - 1) // per_page)
    d.text((120, 212), f"Page {page+1}/{total_pages}", font=_font(12), fill=GRY, anchor="mm")
    d.text((6, 226),   "K1 Rate  K2 Next  K3 Home",  font=_font(11), fill=GRY)
    return img


def screen_rate(score: int) -> Image.Image:
    """RL feedback rating screen — score 1–5."""
    img = Image.new("RGB", (240, 240), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, 240, 28], fill=YEL)
    d.text((120, 14), "Rate Response", font=_font(14, True), fill=INK, anchor="mm")
    d.text((120, 90),  "How helpful was", font=_font(16), fill=WHT, anchor="mm")
    d.text((120, 112), "SHAPE's answer?",  font=_font(16), fill=WHT, anchor="mm")
    stars = "★" * score + "☆" * (5 - score)
    d.text((120, 148), stars, font=_font(28, True), fill=YEL, anchor="mm")
    d.text((120, 185), f"{score} / 5", font=_font(18), fill=YEL, anchor="mm")
    d.text((6,   220), "JOY←→ adjust  PRE confirm", font=_font(11), fill=GRY)
    return img


def screen_status(model: str, avg_score: float | None, records: int) -> Image.Image:
    """Status screen shown when K2 pressed from home."""
    img = Image.new("RGB", (240, 240), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, 240, 28], fill=TEAL)
    d.text((120, 14), "SHAPE Status", font=_font(14, True), fill=INK, anchor="mm")
    rows = [
        ("Model",    model,                        BLUE),
        ("Hardware", "Pi 5 8GB + Zero 2W",         GRY),
        ("Status",   "Online",                     GRN),
        ("RL Records", str(records),               YEL),
        ("Avg Score",  f"{avg_score:.2f}" if avg_score else "N/A", YEL),
        ("Firmware",  "SHAPE v1.0",                GRY),
    ]
    for i, (k, v, col) in enumerate(rows):
        y = 42 + i * 30
        d.text((10,  y), k + ":", font=_font(13),       fill=GRY)
        d.text((230, y), v,       font=_font(13, True),  fill=col, anchor="rm")
    d.text((120, 222), "K3 Back", font=_font(12), fill=GRY, anchor="mm")
    return img
