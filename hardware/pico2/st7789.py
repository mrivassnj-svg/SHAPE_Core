"""
st7789.py — Minimal ST7789 240×240 SPI driver for MicroPython (Pico 2)
Waveshare Pico-LCD-1.3 HAT pin mapping:
  SPI0 CLK  → GP10
  SPI0 MOSI → GP11
  CS        → GP9
  DC        → GP8
  RST       → GP12
  BL        → GP13
"""

import machine
import time
import struct

# ── colour helpers ────────────────────────────────────────────────────────────

def color565(r, g, b):
    """Pack 24-bit RGB into 16-bit RGB565 big-endian."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

BLACK   = color565(0,   0,   0)
WHITE   = color565(255, 255, 255)
VIOLET  = color565(60,  0,   100)
CYAN    = color565(0,   220, 220)
YELLOW  = color565(255, 220, 0)
GREEN   = color565(0,   200, 80)
RED     = color565(220, 40,  40)
ORANGE  = color565(255, 140, 0)

# ── 5×7 bitmap font (ASCII 32-126) ───────────────────────────────────────────
# Each character is 5 bytes; each byte is a column of 7 pixels (bit0=top)
_FONT5X7 = (
    b'\x00\x00\x00\x00\x00'  # 32 space
    b'\x00\x00\x5f\x00\x00'  # 33 !
    b'\x00\x07\x00\x07\x00'  # 34 "
    b'\x14\x7f\x14\x7f\x14'  # 35 #
    b'\x24\x2a\x7f\x2a\x12'  # 36 $
    b'\x23\x13\x08\x64\x62'  # 37 %
    b'\x36\x49\x55\x22\x50'  # 38 &
    b'\x00\x05\x03\x00\x00'  # 39 '
    b'\x00\x1c\x22\x41\x00'  # 40 (
    b'\x00\x41\x22\x1c\x00'  # 41 )
    b'\x14\x08\x3e\x08\x14'  # 42 *
    b'\x08\x08\x3e\x08\x08'  # 43 +
    b'\x00\x50\x30\x00\x00'  # 44 ,
    b'\x08\x08\x08\x08\x08'  # 45 -
    b'\x00\x60\x60\x00\x00'  # 46 .
    b'\x20\x10\x08\x04\x02'  # 47 /
    b'\x3e\x51\x49\x45\x3e'  # 48 0
    b'\x00\x42\x7f\x40\x00'  # 49 1
    b'\x42\x61\x51\x49\x46'  # 50 2
    b'\x21\x41\x45\x4b\x31'  # 51 3
    b'\x18\x14\x12\x7f\x10'  # 52 4
    b'\x27\x45\x45\x45\x39'  # 53 5
    b'\x3c\x4a\x49\x49\x30'  # 54 6
    b'\x01\x71\x09\x05\x03'  # 55 7
    b'\x36\x49\x49\x49\x36'  # 56 8
    b'\x06\x49\x49\x29\x1e'  # 57 9
    b'\x00\x36\x36\x00\x00'  # 58 :
    b'\x00\x56\x36\x00\x00'  # 59 ;
    b'\x08\x14\x22\x41\x00'  # 60 <
    b'\x14\x14\x14\x14\x14'  # 61 =
    b'\x00\x41\x22\x14\x08'  # 62 >
    b'\x02\x01\x51\x09\x06'  # 63 ?
    b'\x32\x49\x79\x41\x3e'  # 64 @
    b'\x7e\x11\x11\x11\x7e'  # 65 A
    b'\x7f\x49\x49\x49\x36'  # 66 B
    b'\x3e\x41\x41\x41\x22'  # 67 C
    b'\x7f\x41\x41\x22\x1c'  # 68 D
    b'\x7f\x49\x49\x49\x41'  # 69 E
    b'\x7f\x09\x09\x09\x01'  # 70 F
    b'\x3e\x41\x49\x49\x7a'  # 71 G
    b'\x7f\x08\x08\x08\x7f'  # 72 H
    b'\x00\x41\x7f\x41\x00'  # 73 I
    b'\x20\x40\x41\x3f\x01'  # 74 J
    b'\x7f\x08\x14\x22\x41'  # 75 K
    b'\x7f\x40\x40\x40\x40'  # 76 L
    b'\x7f\x02\x0c\x02\x7f'  # 77 M
    b'\x7f\x04\x08\x10\x7f'  # 78 N
    b'\x3e\x41\x41\x41\x3e'  # 79 O
    b'\x7f\x09\x09\x09\x06'  # 80 P
    b'\x3e\x41\x51\x21\x5e'  # 81 Q
    b'\x7f\x09\x19\x29\x46'  # 82 R
    b'\x46\x49\x49\x49\x31'  # 83 S
    b'\x01\x01\x7f\x01\x01'  # 84 T
    b'\x3f\x40\x40\x40\x3f'  # 85 U
    b'\x1f\x20\x40\x20\x1f'  # 86 V
    b'\x3f\x40\x38\x40\x3f'  # 87 W
    b'\x63\x14\x08\x14\x63'  # 88 X
    b'\x07\x08\x70\x08\x07'  # 89 Y
    b'\x61\x51\x49\x45\x43'  # 90 Z
    b'\x00\x7f\x41\x41\x00'  # 91 [
    b'\x02\x04\x08\x10\x20'  # 92 backslash
    b'\x00\x41\x41\x7f\x00'  # 93 ]
    b'\x04\x02\x01\x02\x04'  # 94 ^
    b'\x40\x40\x40\x40\x40'  # 95 _
    b'\x00\x01\x02\x04\x00'  # 96 `
    b'\x20\x54\x54\x54\x78'  # 97 a
    b'\x7f\x48\x44\x44\x38'  # 98 b
    b'\x38\x44\x44\x44\x20'  # 99 c
    b'\x38\x44\x44\x48\x7f'  # 100 d
    b'\x38\x54\x54\x54\x18'  # 101 e
    b'\x08\x7e\x09\x01\x02'  # 102 f
    b'\x0c\x52\x52\x52\x3e'  # 103 g
    b'\x7f\x08\x04\x04\x78'  # 104 h
    b'\x00\x44\x7d\x40\x00'  # 105 i
    b'\x20\x40\x44\x3d\x00'  # 106 j
    b'\x7f\x10\x28\x44\x00'  # 107 k
    b'\x00\x41\x7f\x40\x00'  # 108 l
    b'\x7c\x04\x18\x04\x78'  # 109 m
    b'\x7c\x08\x04\x04\x78'  # 110 n
    b'\x38\x44\x44\x44\x38'  # 111 o
    b'\x7c\x14\x14\x14\x08'  # 112 p
    b'\x08\x14\x14\x18\x7c'  # 113 q
    b'\x7c\x08\x04\x04\x08'  # 114 r
    b'\x48\x54\x54\x54\x20'  # 115 s
    b'\x04\x3f\x44\x40\x20'  # 116 t
    b'\x3c\x40\x40\x20\x7c'  # 117 u
    b'\x1c\x20\x40\x20\x1c'  # 118 v
    b'\x3c\x40\x30\x40\x3c'  # 119 w
    b'\x44\x28\x10\x28\x44'  # 120 x
    b'\x0c\x50\x50\x50\x3c'  # 121 y
    b'\x44\x64\x54\x4c\x44'  # 122 z
    b'\x00\x08\x36\x41\x00'  # 123 {
    b'\x00\x00\x7f\x00\x00'  # 124 |
    b'\x00\x41\x36\x08\x00'  # 125 }
    b'\x10\x08\x08\x10\x08'  # 126 ~
)


class ST7789:
    """Minimal ST7789 driver for Waveshare Pico-LCD-1.3 (240×240)."""

    WIDTH  = 240
    HEIGHT = 240

    def __init__(self):
        self._spi = machine.SPI(1, baudrate=40_000_000,
                                polarity=0, phase=0,
                                sck=machine.Pin(10),
                                mosi=machine.Pin(11))
        self._cs  = machine.Pin(9,  machine.Pin.OUT, value=1)
        self._dc  = machine.Pin(8,  machine.Pin.OUT, value=1)
        self._rst = machine.Pin(12, machine.Pin.OUT, value=1)
        self._bl  = machine.Pin(13, machine.Pin.OUT, value=1)
        self._init()

    # ── low-level ──────────────────────────────────────────────────────────

    def _cmd(self, c):
        self._dc.value(0); self._cs.value(0)
        self._spi.write(bytes([c]))
        self._cs.value(1)

    def _dat(self, d):
        self._dc.value(1); self._cs.value(0)
        self._spi.write(d if isinstance(d, (bytes, bytearray)) else bytes([d]))
        self._cs.value(1)

    def _init(self):
        self._rst.value(0); time.sleep_ms(50)
        self._rst.value(1); time.sleep_ms(50)
        for c, d in (
            (0x11, None),          # Sleep out
            (0x36, b'\x70'),       # MADCTL
            (0x3A, b'\x05'),       # COLMOD 16-bit
            (0xB2, b'\x0C\x0C\x00\x33\x33'),
            (0xB7, b'\x35'),
            (0xBB, b'\x19'),
            (0xC0, b'\x2C'),
            (0xC2, b'\x01'),
            (0xC3, b'\x12'),
            (0xC4, b'\x20'),
            (0xC6, b'\x0F'),
            (0xD0, b'\xA4\xA1'),
            (0x29, None),          # Display on
        ):
            time.sleep_ms(5 if c == 0x11 else 0)
            self._cmd(c)
            if d: self._dat(d)
        self.fill(BLACK)

    def _set_window(self, x0, y0, x1, y1):
        self._cmd(0x2A); self._dat(struct.pack('>HH', x0, x1))
        self._cmd(0x2B); self._dat(struct.pack('>HH', y0, y1))
        self._cmd(0x2C)

    # ── drawing API ────────────────────────────────────────────────────────

    def fill(self, color):
        self._set_window(0, 0, self.WIDTH - 1, self.HEIGHT - 1)
        chunk = struct.pack('>H', color) * 128
        self._dc.value(1); self._cs.value(0)
        for _ in range(self.WIDTH * self.HEIGHT // 128):
            self._spi.write(chunk)
        self._cs.value(1)

    def pixel(self, x, y, color):
        self._set_window(x, y, x, y)
        self._dat(struct.pack('>H', color))

    def rect(self, x, y, w, h, color):
        self._set_window(x, y, x + w - 1, y + h - 1)
        chunk = struct.pack('>H', color) * min(w, 64)
        self._dc.value(1); self._cs.value(0)
        for _ in range(w * h // min(w, 64)):
            self._spi.write(chunk)
        self._cs.value(1)

    def hline(self, x, y, w, color):
        self.rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.rect(x, y, 1, h, color)

    def char(self, x, y, ch, color, bg=BLACK, scale=1):
        """Draw a single ASCII character using the built-in 5×7 font."""
        c = ord(ch)
        if c < 32 or c > 126:
            c = 32
        base = (c - 32) * 5
        for col in range(5):
            bits = _FONT5X7[base + col]
            for row in range(7):
                px_color = color if (bits >> row) & 1 else bg
                if scale == 1:
                    self.pixel(x + col, y + row, px_color)
                else:
                    self.rect(x + col * scale, y + row * scale,
                               scale, scale, px_color)

    def text(self, x, y, s, color, bg=BLACK, scale=1):
        """Draw a string; wraps at display width."""
        cx = x
        for ch in s:
            if cx + 6 * scale > self.WIDTH:
                cx = x; y += 9 * scale
            self.char(cx, y, ch, color, bg, scale)
            cx += 6 * scale

    def text_center(self, y, s, color, bg=BLACK, scale=1):
        """Draw a string centred horizontally."""
        w = len(s) * 6 * scale
        x = max(0, (self.WIDTH - w) // 2)
        self.text(x, y, s, color, bg, scale)
