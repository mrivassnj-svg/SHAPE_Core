"""
render_setup_videos.py — SHAPE Hardware Setup Tutorial Videos
==============================================================
Produces three MP4 videos, one per hardware tier:

  setup_tier1_pico2.mp4   — Pico 2 flash + GPIO wiring + sensor test
  setup_tier2_zero2w.mp4  — Zero 2 W UART config + HAT + run terminal
  setup_tier3_pi5.mp4     — Pi 5 Ollama install + SHAPE agent + API server

Each video is a sequence of annotated instructional frames rendered with
Pillow and assembled by ffmpeg. No Blender, no GPU, no internet needed.

Usage:
    python demo/render_setup_videos.py

Output:
    demo/output/setup_tier1_pico2.mp4
    demo/output/setup_tier2_zero2w.mp4
    demo/output/setup_tier3_pi5.mp4

Group 3 — ITAI2376-14562
Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas
"""

from __future__ import annotations
import subprocess, sys, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 1280, 720

# ── Palette ───────────────────────────────────────────────────────────────────
BG    = ( 10,   8,  26)
PANEL = ( 20,  18,  48)
TERM  = (  5,  10,   5)
WIRE  = ( 15,  15,  40)
BLUE  = ( 25, 140, 255)
CYAN  = (  0, 220, 210)
GRN   = ( 20, 255, 115)
YEL   = (255, 220,   0)
ORG   = (255, 115,   0)
RED   = (255,  50,  50)
WHT   = (235, 235, 245)
GRY   = (120, 120, 150)
DIM   = ( 70,  70, 100)
PINK  = (255,  60, 150)

FONT   = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS   = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SBOLD  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def fnt(size, bold=False, mono=True):
    path = (BOLD if bold else FONT) if mono else (SBOLD if bold else SANS)
    try: return ImageFont.truetype(path, size)
    except: return ImageFont.load_default()

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_setup_frames"
TMP.mkdir(exist_ok=True)

# ── Primitives ────────────────────────────────────────────────────────────────

def slide():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def header(d, tier_num, tier_name, color, step=None, total=None):
    # top bar
    d.rectangle([0, 0, W, 52], fill=PANEL)
    d.rectangle([0, 52, W, 54], fill=color)
    # tier badge
    badge = f"TIER {tier_num}"
    d.rectangle([16, 10, 110, 42], fill=color)
    d.text((18, 13), badge, font=fnt(16, bold=True), fill=BG)
    d.text((120, 11), tier_name, font=fnt(22, bold=True, mono=False), fill=WHT)
    # step indicator
    if step and total:
        label = f"Step {step} of {total}"
        bbox  = d.textbbox((0,0), label, font=fnt(14))
        tw    = bbox[2]-bbox[0]
        d.text((W - tw - 20, 18), label, font=fnt(14), fill=GRY)

def footer(d, msg=""):
    d.rectangle([0, H-36, W, H], fill=PANEL)
    d.rectangle([0, H-36, W, H-34], fill=DIM)
    left = "Group 3 | ITAI2376-14562  ·  Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas"
    d.text((16, H-26), left, font=fnt(11), fill=DIM)
    if msg:
        bbox = d.textbbox((0,0), msg, font=fnt(11))
        tw   = bbox[2]-bbox[0]
        d.text((W-tw-16, H-26), msg, font=fnt(11), fill=GRY)

def section_title(d, y, text, color=CYAN):
    d.text((32, y), text, font=fnt(18, bold=True, mono=False), fill=color)
    d.rectangle([32, y+26, W-32, y+28], fill=color)

def term_block(d, x, y, w, h, lines, title="Terminal", cursor=True):
    """Render a terminal window block."""
    d.rectangle([x, y, x+w, y+h], fill=TERM)
    d.rectangle([x, y, x+w, y+22], fill=(20, 40, 20))
    d.rectangle([x, y+22, x+w, y+24], fill=(40, 80, 40))
    # traffic lights
    for cx, col in [(x+10, (255,80,80)), (x+28, (255,190,0)), (x+46, (100,200,80))]:
        d.ellipse([cx-5, y+6, cx+5, y+16], fill=col)
    d.text((x+62, y+5), title, font=fnt(12), fill=(120,160,120))
    yy = y + 32
    lh = 16
    for line in lines:
        if yy + lh > y + h - 4: break
        if line.startswith("$ "):
            d.text((x+10, yy), line, font=fnt(13, bold=True), fill=GRN)
        elif line.startswith("#"):
            d.text((x+10, yy), line, font=fnt(13), fill=GRY)
        elif line.startswith("✓") or line.startswith("OK") or "done" in line.lower():
            d.text((x+10, yy), line, font=fnt(13), fill=GRN)
        elif line.startswith("!") or "error" in line.lower():
            d.text((x+10, yy), line, font=fnt(13), fill=RED)
        elif line.startswith(">>>"):
            d.text((x+10, yy), line, font=fnt(13), fill=CYAN)
        else:
            d.text((x+10, yy), line, font=fnt(13), fill=(160, 220, 160))
        yy += lh
    if cursor and yy < y + h - 4:
        d.rectangle([x+10, yy+2, x+18, yy+14], fill=GRN)

def code_block(d, x, y, w, h, lines, title=""):
    d.rectangle([x, y, x+w, y+h], fill=(14, 14, 28))
    d.rectangle([x, y, x+w, y+20], fill=(25, 25, 50))
    if title:
        d.text((x+8, y+4), title, font=fnt(11), fill=GRY)
    yy = y + 28
    lh = 15
    kw = {"def","import","from","return","if","else","for","while","class","print","True","False","None"}
    for line in lines:
        if yy + lh > y + h - 4: break
        words = line.split()
        x0 = x + 10
        indent = len(line) - len(line.lstrip())
        x0 += indent * 7
        clean = line.strip()
        if clean.startswith("#"):
            d.text((x+10+indent*7, yy), clean, font=fnt(13), fill=(80,120,80))
        elif any(clean.startswith(k+" ") or clean==k for k in kw):
            d.text((x+10+indent*7, yy), clean, font=fnt(13, bold=True), fill=CYAN)
        elif clean.startswith('"') or clean.startswith("'"):
            d.text((x+10+indent*7, yy), clean, font=fnt(13), fill=ORG)
        else:
            d.text((x+10+indent*7, yy), clean, font=fnt(13), fill=WHT)
        yy += lh

def gpio_pin(d, x, y, num, signal, color):
    d.rounded_rectangle([x, y, x+36, y+20], radius=3, fill=color)
    d.text((x+4, y+3), f"GP{num:02d}", font=fnt(10, bold=True), fill=BG)
    d.text((x+42, y+3), signal, font=fnt(11), fill=WHT)

def wire(d, x1, y1, x2, y2, color):
    d.line([x1,y1,x2,y2], fill=color, width=3)

def callout_box(d, x, y, w, lines, color=YEL):
    h = 14 + len(lines) * 18
    d.rounded_rectangle([x, y, x+w, y+h], radius=5, fill=(30,25,8))
    d.rounded_rectangle([x, y, x+w, y+h], radius=5, outline=color, width=2)
    d.rectangle([x, y, x+8, y+h], fill=color)
    for i, line in enumerate(lines):
        d.text((x+16, y+7+i*18), line, font=fnt(13, mono=False), fill=WHT)

def pill(d, x, y, text, bg, fg=BG):
    bbox = d.textbbox((0,0), text, font=fnt(12, bold=True))
    tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
    d.rounded_rectangle([x, y, x+tw+16, y+th+8], radius=4, fill=bg)
    d.text((x+8, y+4), text, font=fnt(12, bold=True), fill=fg)
    return tw+16

def checklist(d, x, y, items):
    """items: list of (done, text)"""
    for done, text in items:
        icon = "✓" if done else "○"
        col  = GRN  if done else GRY
        d.text((x, y), icon, font=fnt(16, bold=True), fill=col)
        d.text((x+22, y+2), text, font=fnt(14, mono=False),
               fill=WHT if done else GRY)
        y += 26

def save_frames(frames, prefix, fps=30):
    """Save a list of (img, duration_s) to numbered PNGs, return paths + durations."""
    paths = []
    for i, (img, dur) in enumerate(frames):
        p = TMP / f"{prefix}_{i:03d}.png"
        img.save(p)
        paths.append((p, dur))
    return paths

def assemble(frame_pairs, out_path):
    concat = TMP / f"{out_path.stem}_concat.txt"
    with open(concat, "w") as f:
        for p, dur in frame_pairs:
            f.write(f"file '{p.resolve()}'\n")
            f.write(f"duration {dur}\n")
    r = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", "scale=1280:720,fps=30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", str(out_path)
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg error:", r.stderr[-400:])
        sys.exit(1)
    mb = out_path.stat().st_size / 1_048_576
    total_s = sum(d for _,d in frame_pairs)
    print(f"  ✓  {out_path.name}  ({total_s:.0f}s, {mb:.1f} MB)")


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1 — Raspberry Pi Pico 2 Setup
# ═══════════════════════════════════════════════════════════════════════════════

def tier1_frames():
    frames = []

    # ── Slide 1: Title ────────────────────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — Sensor Node Setup", CYAN, 0, 0)
    footer(d, "Tier 1 of 3")
    # large title
    d.text((W//2 - 320, 130), "SHAPE Hardware Setup", font=fnt(38, bold=True, mono=False), fill=WHT)
    d.text((W//2 - 220, 182), "Tier 1 · Pico 2 (RP2350)", font=fnt(26, bold=True, mono=False), fill=CYAN)
    d.rectangle([W//2-220, 220, W//2+220, 222], fill=CYAN)
    items = [
        "Flash MicroPython firmware onto the Pico 2",
        "Wire DHT22 temperature/humidity sensor",
        "Wire MQ-135 air quality sensor",
        "Copy SHAPE firmware files via mpremote",
        "Verify UART telemetry output",
    ]
    for i, item in enumerate(items):
        d.text((W//2 - 220, 240 + i*36), f"  {i+1}.", font=fnt(18, bold=True), fill=CYAN)
        d.text((W//2 - 190, 240 + i*36), item, font=fnt(18, mono=False), fill=WHT)
    frames.append((img, 4))

    # ── Slide 2: Hardware checklist ───────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — Hardware Required", CYAN, 1, 6)
    footer(d, "Tier 1 · Step 1 of 6")
    section_title(d, 70, "Hardware You Need", CYAN)
    items = [
        ("Raspberry Pi Pico 2 (RP2350)",     ORG),
        ("Waveshare Pico-LCD-1.3 HAT",        CYAN),
        ("DHT22 temperature/humidity sensor", GRN),
        ("MQ-135 air quality sensor",         YEL),
        ("Micro USB cable (data, not charge-only)", WHT),
        ("3× female-to-female jumper wires",  GRY),
        ("Breadboard (optional)",             DIM),
    ]
    y = 110
    for name, col in items:
        d.rectangle([32, y+4, 44, y+16], fill=col)
        d.text((56, y), name, font=fnt(18, mono=False), fill=WHT)
        y += 34
    callout_box(d, 650, 110, 580, [
        "The HAT plugs directly onto the Pico 2",
        "40-pin header — no soldering needed.",
        "Sensors connect to the exposed GPIO",
        "breakout pins on the bottom of the HAT.",
    ], YEL)
    frames.append((img, 5))

    # ── Slide 3: Flash MicroPython ────────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — Flash MicroPython", CYAN, 2, 6)
    footer(d, "Tier 1 · Step 2 of 6")
    section_title(d, 70, "Flash MicroPython Firmware", CYAN)
    term_block(d, 32, 110, 760, 200, [
        "# 1. Download MicroPython UF2 for RP2350:",
        "$ wget https://micropython.org/download/RPI_PICO2/",
        "#    (download RPI_PICO2-*.uf2)",
        "",
        "# 2. Hold BOOTSEL button on Pico 2,",
        "#    then plug in USB — a drive appears: RPI-RP2",
        "",
        "# 3. Drag the .uf2 file onto the RPI-RP2 drive",
        "#    Pico reboots automatically with MicroPython",
        "",
        "# 4. Verify:",
        "$ python3 -m mpremote connect /dev/ttyACM0 repl",
        ">>> print('MicroPython OK')",
        "MicroPython OK",
        "✓ MicroPython running on Pico 2",
    ], title="bash — your laptop")
    callout_box(d, 820, 110, 420, [
        "If /dev/ttyACM0 is not found,",
        "try /dev/ttyACM1 or check:",
        "  ls /dev/tty*",
        "On macOS use /dev/cu.usbmodem*",
        "",
        "mpremote install:",
        "  pip install mpremote",
    ], CYAN)
    frames.append((img, 7))

    # ── Slide 4: GPIO wiring diagram ──────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — GPIO Wiring", CYAN, 3, 6)
    footer(d, "Tier 1 · Step 3 of 6")
    section_title(d, 70, "GPIO Wiring — DHT22 + MQ-135 + UART", CYAN)

    # Pico board outline
    bx, by = 180, 110
    d.rounded_rectangle([bx, by, bx+200, by+340], radius=8, fill=(30,50,20), outline=GRN, width=2)
    d.text((bx+30, by+6), "Pico 2 (RP2350)", font=fnt(12, bold=True), fill=GRN)

    pins = [
        (0, "GP0 TX", GRY),    (1, "GP1 RX", GRY),
        (2, "GP2  ", GRY),     (3, "3V3    ", ORG),
        (4, "GND  ", DIM),     (5, "GP22   ", GRN),
        (6, "GP26 A", YEL),    (7, "GP27 D", YEL),
        (8, "VBUS  ", RED),
    ]
    for i, (num, label, col) in enumerate(pins):
        py = by + 36 + i * 30
        d.rectangle([bx+170, py, bx+198, py+16], fill=col)
        d.text((bx+104, py+1), label, font=fnt(11), fill=col)

    # Wires and labels
    # DHT22
    d.text((520, 112), "DHT22", font=fnt(16, bold=True, mono=False), fill=GRN)
    d.rounded_rectangle([510, 134, 660, 220], radius=5, fill=(20,40,20), outline=GRN, width=2)
    for i, (sig, pin) in enumerate([("VCC → 3V3", ORG), ("GND → GND", DIM), ("DATA → GP22", GRN)]):
        wire(d, bx+198, by+36+2*30+8, 510, 148+i*22, ORG if "3V3" in sig else (DIM if "GND" in sig else GRN))
        d.text((520, 148+i*22), sig, font=fnt(13), fill=ORG if "3V3" in sig else (DIM if "GND" in sig else GRN))

    # MQ-135
    d.text((520, 260), "MQ-135", font=fnt(16, bold=True, mono=False), fill=YEL)
    d.rounded_rectangle([510, 282, 660, 380], radius=5, fill=(30,25,5), outline=YEL, width=2)
    for i, (sig, col) in enumerate([("VCC → VBUS(5V)", RED), ("GND → GND", DIM), ("AOUT → GP26", YEL), ("DOUT → GP27", YEL)]):
        d.text((520, 294+i*20), sig, font=fnt(12), fill=col)

    # UART
    d.text((780, 112), "UART to Zero 2 W", font=fnt(15, bold=True, mono=False), fill=GRY)
    d.rounded_rectangle([770, 134, 1000, 210], radius=5, fill=WIRE, outline=GRY, width=2)
    for i, (sig, col) in enumerate([("GP0 TX → Zero2W GPIO15 (RX)", GRY), ("GP1 RX → Zero2W GPIO14 (TX)", GRY), ("GND → GND (shared)", DIM)]):
        d.text((780, 148+i*18), sig, font=fnt(12), fill=col)

    callout_box(d, 770, 240, 460, [
        "⚠  DO NOT connect 5V to GP pins",
        "Pico 2 is 3.3 V logic.",
        "MQ-135 power uses VBUS (5V),",
        "but its signal pins are 3.3V-safe.",
    ], RED)
    frames.append((img, 8))

    # ── Slide 5: Copy firmware files ──────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — Copy Firmware Files", CYAN, 4, 6)
    footer(d, "Tier 1 · Step 4 of 6")
    section_title(d, 70, "Copy SHAPE Firmware via mpremote", CYAN)
    term_block(d, 32, 110, 760, 310, [
        "# From your laptop in the SHAPE_Core directory:",
        "$ cd /path/to/SHAPE_Core",
        "",
        "# Copy all firmware files to Pico 2 flash:",
        "$ mpremote connect /dev/ttyACM0 fs cp \\",
        "    hardware/pico2/boot.py    :boot.py",
        "$ mpremote connect /dev/ttyACM0 fs cp \\",
        "    hardware/pico2/st7789.py  :st7789.py",
        "$ mpremote connect /dev/ttyACM0 fs cp \\",
        "    hardware/pico2/sensors.py :sensors.py",
        "$ mpremote connect /dev/ttyACM0 fs cp \\",
        "    hardware/pico2/keys.py    :keys.py",
        "$ mpremote connect /dev/ttyACM0 fs cp \\",
        "    hardware/pico2/main.py    :main.py",
        "",
        "# Reset to start the firmware:",
        "$ mpremote connect /dev/ttyACM0 reset",
        "✓ LCD lights up — SHAPE SENSOR NODE header visible",
    ], title="bash — your laptop")
    code_block(d, 820, 110, 420, 230, [
        "# hardware/pico2/main.py",
        "# Main loop (runs on Pico 2)",
        "",
        "while True:",
        "    now = ticks_ms()",
        "    evt = keys.poll()",
        "    if ticks_diff(now,last) >= 2000:",
        "        hub.measure()",
        "        _send_csv(now, hub)",
        "        last = now",
        "    msg = _recv_json()",
        "    if ticks_diff(now,draw_t) >= 250:",
        "        draw_sensor_screen(...)",
        "        draw_t = now",
        "    sleep_ms(10)",
    ], title="hardware/pico2/main.py")
    frames.append((img, 8))

    # ── Slide 6: Verify UART output ───────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — Verify Output", CYAN, 5, 6)
    footer(d, "Tier 1 · Step 5 of 6")
    section_title(d, 70, "Verify UART Telemetry Output", CYAN)
    term_block(d, 32, 110, 760, 220, [
        "# Monitor UART output from Pico 2:",
        "$ mpremote connect /dev/ttyACM0 repl",
        "",
        "# Or use minicom / screen:",
        "$ minicom -b 115200 -D /dev/ttyACM0",
        "",
        "# You should see CSV lines every 2 seconds:",
        "SHAPE,2000,22.40,58.1,312,0",
        "SHAPE,4000,23.10,57.4,318,0",
        "SHAPE,6000,22.80,58.0,325,0",
        "# Format: SHAPE,ts_ms,temp,humidity,aqi,alert",
        "✓ Pico 2 Tier 1 is operational",
    ], title="bash — monitoring UART from laptop")
    callout_box(d, 820, 110, 420, [
        "Expected LCD behaviour:",
        "",
        "SENSOR mode (default):",
        "  TEMP: 22.4C",
        "  RH:   58.1%",
        "  AQI:  312",
        "",
        "Press A to cycle modes:",
        "  SENSOR → STATUS → RESPONSE",
        "",
        "Press B to force immediate",
        "sensor read + UART transmit",
    ], CYAN)
    # Simulated LCD
    lcd_x, lcd_y = 820, 350
    d.rectangle([lcd_x, lcd_y, lcd_x+180, lcd_y+180], fill=(20,0,40), outline=CYAN, width=2)
    d.rectangle([lcd_x, lcd_y, lcd_x+180, lcd_y+22], fill=(30,0,60))
    d.text((lcd_x+8, lcd_y+5), "SHAPE SENSOR NODE", font=fnt(10, bold=True), fill=CYAN)
    d.text((lcd_x+8, lcd_y+34), "TEMP", font=fnt(10), fill=GRY)
    d.text((lcd_x+60, lcd_y+30), "22.4C", font=fnt(18, bold=True), fill=GRN)
    d.text((lcd_x+8, lcd_y+58), "RH  ", font=fnt(10), fill=GRY)
    d.text((lcd_x+60, lcd_y+54), "58.1%", font=fnt(18, bold=True), fill=WHT)
    d.text((lcd_x+8, lcd_y+82), "AQI ", font=fnt(10), fill=GRY)
    d.text((lcd_x+60, lcd_y+78), "312", font=fnt(18, bold=True), fill=GRN)
    d.rectangle([lcd_x+8, lcd_y+108, lcd_x+172, lcd_y+114], fill=GRY)
    d.rectangle([lcd_x+8, lcd_y+108, lcd_x+8+int(312/1000*164), lcd_y+114], fill=GRN)
    frames.append((img, 7))

    # ── Slide 7: Checklist complete ───────────────────────────────────────────
    img, d = slide()
    header(d, 1, "Raspberry Pi Pico 2 — Setup Complete", CYAN, 6, 6)
    footer(d, "Tier 1 complete — proceed to Tier 2")
    section_title(d, 70, "Tier 1 Setup Complete", GRN)
    checklist(d, 60, 115, [
        (True,  "MicroPython flashed onto Pico 2"),
        (True,  "DHT22 wired: VCC→3V3, GND→GND, DATA→GP22"),
        (True,  "MQ-135 wired: VCC→VBUS, GND→GND, AOUT→GP26, DOUT→GP27"),
        (True,  "UART wired: GP0(TX)→Zero2W GPIO15, GP1(RX)→Zero2W GPIO14"),
        (True,  "Firmware files copied via mpremote"),
        (True,  "LCD shows SHAPE SENSOR NODE with live readings"),
        (True,  "UART outputs CSV every 2 s: SHAPE,ts,temp,humidity,aqi,alert"),
    ])
    d.text((60, 420), "→  Next: Tier 2 — Raspberry Pi Zero 2 W setup", font=fnt(18, bold=True, mono=False), fill=CYAN)
    frames.append((img, 5))

    return frames


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2 — Raspberry Pi Zero 2 W Setup
# ═══════════════════════════════════════════════════════════════════════════════

def tier2_frames():
    frames = []

    # ── Slide 1: Title ────────────────────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Raspberry Pi Zero 2 W — Field Terminal Setup", PINK, 0, 0)
    footer(d, "Tier 2 of 3")
    d.text((W//2 - 300, 130), "SHAPE Hardware Setup", font=fnt(38, bold=True, mono=False), fill=WHT)
    d.text((W//2 - 265, 182), "Tier 2 · Raspberry Pi Zero 2 W", font=fnt(24, bold=True, mono=False), fill=PINK)
    d.rectangle([W//2-265, 220, W//2+265, 222], fill=PINK)
    items = [
        "Install Raspberry Pi OS Lite (64-bit) on SD card",
        "Enable UART, disable Bluetooth overlay",
        "Install Python dependencies + pyserial",
        "Set Pi 5 IP in environment variables",
        "Copy and run main_zero2w.py",
        "Verify LCD shows HOME screen and K1/K2/K3 respond",
    ]
    for i, item in enumerate(items):
        d.text((W//2 - 265, 240 + i*34), f"  {i+1}.", font=fnt(17, bold=True), fill=PINK)
        d.text((W//2 - 238, 240 + i*34), item, font=fnt(17, mono=False), fill=WHT)
    frames.append((img, 4))

    # ── Slide 2: OS install ───────────────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Zero 2 W — OS Install", PINK, 1, 6)
    footer(d, "Tier 2 · Step 1 of 6")
    section_title(d, 70, "Install Raspberry Pi OS Lite (64-bit)", PINK)
    term_block(d, 32, 110, 760, 220, [
        "# Use Raspberry Pi Imager on your laptop:",
        "# rpi.imager.download → install → open",
        "",
        "# Select: Raspberry Pi Zero 2 W",
        "# OS: Raspberry Pi OS Lite (64-bit)",
        "# Storage: your micro SD card (≥8 GB)",
        "",
        "# In Advanced settings (gear icon):",
        "#   ✓ Enable SSH",
        "#   ✓ Set username: pi",
        "#   ✓ Set Wi-Fi SSID + password (same as Pi 5)",
        "#   ✓ Set hostname: shape-zero",
        "",
        "# Flash, then boot Zero 2 W from SD",
        "✓ SSH available: ssh pi@shape-zero.local",
    ], title="bash — your laptop")
    callout_box(d, 820, 110, 420, [
        "Raspberry Pi Imager download:",
        "  raspberrypi.com/software",
        "",
        "Both Zero 2 W and Pi 5 must be",
        "on the SAME Wi-Fi network so",
        "HTTP calls to 192.168.4.1:8765",
        "(Pi 5 IP) work from the Zero.",
        "",
        "Assign a static IP to the Pi 5",
        "in your router for reliability.",
    ], PINK)
    frames.append((img, 7))

    # ── Slide 3: Enable UART ──────────────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Zero 2 W — Enable UART + Disable Bluetooth", PINK, 2, 6)
    footer(d, "Tier 2 · Step 2 of 6")
    section_title(d, 70, "Enable UART, Disable Bluetooth Overlay", PINK)
    term_block(d, 32, 110, 760, 300, [
        "# SSH into the Zero 2 W:",
        "$ ssh pi@shape-zero.local",
        "",
        "# Edit /boot/config.txt:",
        "$ sudo nano /boot/config.txt",
        "",
        "# Add these lines at the end:",
        "enable_uart=1",
        "dtoverlay=disable-bt",
        "",
        "# Save (Ctrl+X, Y, Enter), then disable hciuart:",
        "$ sudo systemctl disable hciuart",
        "Removed /etc/systemd/system/bluetooth.target.wants/hciuart.service",
        "",
        "# Reboot:",
        "$ sudo reboot",
        "",
        "# After reboot, verify UART is free:",
        "$ ls -la /dev/ttyAMA*",
        "crw-rw---- 1 root dialout ... /dev/ttyAMA1",
        "✓ UART1 (/dev/ttyAMA1) available for Pico 2",
    ], title="ssh pi@shape-zero.local")
    callout_box(d, 820, 110, 420, [
        "Why disable Bluetooth?",
        "",
        "The Pi Zero 2 W has one full",
        "PL011 UART. By default it's",
        "used by Bluetooth. We need it",
        "for the Pico 2 serial bridge.",
        "",
        "dtoverlay=disable-bt frees",
        "it and maps it to GPIO14/15.",
        "",
        "GPIO14 = UART TX → Pico GP1",
        "GPIO15 = UART RX → Pico GP0",
    ], YEL)
    frames.append((img, 8))

    # ── Slide 4: Install Python deps ──────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Zero 2 W — Install Dependencies", PINK, 3, 6)
    footer(d, "Tier 2 · Step 3 of 6")
    section_title(d, 70, "Install Python Dependencies", PINK)
    term_block(d, 32, 110, 760, 300, [
        "$ ssh pi@shape-zero.local",
        "",
        "# Update and install system packages:",
        "$ sudo apt-get update && sudo apt-get install -y \\",
        "    python3-pip python3-pil libjpeg-dev",
        "",
        "# Clone SHAPE_Core:",
        "$ git clone https://github.com/mrivassnj-svg/SHAPE_Core.git",
        "$ cd SHAPE_Core",
        "",
        "# Install Python requirements:",
        "$ pip3 install pyserial requests pillow",
        "",
        "# Set Pi 5 IP (replace with your Pi 5 static IP):",
        "$ echo 'export SHAPE_PI5_URL=http://192.168.1.100:8765' >> ~/.bashrc",
        "$ echo 'export SHAPE_API_KEY=shape_local_key' >> ~/.bashrc",
        "$ source ~/.bashrc",
        "",
        "✓ Dependencies installed",
    ], title="ssh pi@shape-zero.local")
    callout_box(d, 820, 110, 420, [
        "Find your Pi 5 IP address:",
        "  ssh pi@shape-pi5.local",
        "  hostname -I",
        "",
        "Or check your router's",
        "connected devices list.",
        "",
        "The API key must match",
        "config_pi5.yaml api_key:",
        "  shape_local_key (default)",
    ], CYAN)
    frames.append((img, 7))

    # ── Slide 5: Run terminal ─────────────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Zero 2 W — Run Field Terminal", PINK, 4, 6)
    footer(d, "Tier 2 · Step 4 of 6")
    section_title(d, 70, "Run the SHAPE Field Terminal", PINK)
    term_block(d, 32, 110, 760, 220, [
        "$ cd ~/SHAPE_Core",
        "",
        "# Run the terminal (needs HAT connected):",
        "$ python3 hardware/zero2w/main_zero2w.py",
        "",
        "# Expected output:",
        "INFO  shape.zero2w — Pi 5 online: True",
        "INFO  shape.zero2w — ShapeTerminal started",
        "",
        "# To run on boot (optional):",
        "$ crontab -e",
        "# Add: @reboot sleep 10 && cd ~/SHAPE_Core &&",
        "#      python3 hardware/zero2w/main_zero2w.py",
        "",
        "✓ HAT LCD shows HOME screen",
    ], title="ssh pi@shape-zero.local")
    code_block(d, 820, 110, 420, 230, [
        "# Controls summary:",
        "# hardware/zero2w/main_zero2w.py",
        "",
        "# From HOME screen:",
        "#  UP/DOWN  — scroll preset queries",
        "#  K1       — select & send query",
        "#  K2       — system status screen",
        "",
        "# From RESPONSE screen:",
        "#  K1       — rate the response (1-5)",
        "#  K2       — next page",
        "#  K3       — back to HOME",
        "",
        "# Voice input:",
        "#  Hold K3 >= 1 second",
        "#  Speak query (5s recording)",
        "#  Transcribed by Pi 5 whisper",
    ], title="controls")
    frames.append((img, 7))

    # ── Slide 6: Verify ───────────────────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Zero 2 W — Verify Operation", PINK, 5, 6)
    footer(d, "Tier 2 · Step 5 of 6")
    section_title(d, 70, "Verify End-to-End Operation", PINK)

    # State machine diagram
    states = [
        ("HOME",     100, 160, CYAN),
        ("QUERY",    300, 160, YEL),
        ("THINKING", 500, 160, ORG),
        ("RESPONSE", 700, 160, GRN),
        ("RATE",     900, 160, PINK),
    ]
    for name, x, y, col in states:
        d.rounded_rectangle([x-55, y-20, x+55, y+20], radius=8, fill=col)
        d.text((x-40, y-10), name, font=fnt(14, bold=True), fill=BG)

    transitions = [
        (100, 160, 300, 160, "K1"),
        (300, 160, 500, 160, "K1"),
        (500, 160, 700, 160, "auto"),
        (700, 160, 900, 160, "K1"),
        (900, 160, 100, 160, "PRESS"),
    ]
    for x1,y1,x2,y2,label in transitions:
        d.line([x1+55, y1, x2-55, y2], fill=GRY, width=2)
        mx = (x1+x2)//2
        d.text((mx-12, y1-18), label, font=fnt(11), fill=GRY)

    term_block(d, 32, 230, 760, 250, [
        "# Test: press K1 to send first preset query",
        "# Preset: 'Show me the latest sensor readings'",
        "",
        "# Zero 2 W logs (ssh pi@shape-zero.local):",
        "INFO  shape.zero2w — Pi 5 online: True",
        "INFO  shape.zero2w — Query: Show me the latest...",
        "INFO  shape.zero2w — Response received (14.2 s)",
        "",
        "# After response appears on LCD:",
        "# Press K1 to rate → joystick RIGHT to 5 → PRESS",
        "INFO  shape.zero2w — Feedback sent: 5",
        "✓ Full query → response → rating cycle complete",
    ], title="ssh pi@shape-zero.local — monitoring logs")
    frames.append((img, 7))

    # ── Slide 7: Complete ─────────────────────────────────────────────────────
    img, d = slide()
    header(d, 2, "Zero 2 W — Setup Complete", PINK, 6, 6)
    footer(d, "Tier 2 complete — proceed to Tier 3")
    section_title(d, 70, "Tier 2 Setup Complete", GRN)
    checklist(d, 60, 115, [
        (True, "Raspberry Pi OS Lite 64-bit installed"),
        (True, "UART enabled, Bluetooth overlay disabled"),
        (True, "pyserial + requests + pillow installed"),
        (True, "SHAPE_PI5_URL and SHAPE_API_KEY set in .bashrc"),
        (True, "main_zero2w.py runs without errors"),
        (True, "HOME screen visible on HAT LCD"),
        (True, "K1 → QUERY → THINKING → RESPONSE cycle works"),
        (True, "Feedback (K1 → RATE → PRESS) sends to Pi 5"),
    ])
    d.text((60, 410), "→  Next: Tier 3 — Raspberry Pi 5 setup", font=fnt(18, bold=True, mono=False), fill=PINK)
    frames.append((img, 5))

    return frames


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 3 — Raspberry Pi 5 Setup
# ═══════════════════════════════════════════════════════════════════════════════

def tier3_frames():
    frames = []

    # ── Slide 1: Title ────────────────────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Raspberry Pi 5 — SHAPE Agent Server Setup", ORG, 0, 0)
    footer(d, "Tier 3 of 3")
    d.text((W//2 - 300, 130), "SHAPE Hardware Setup", font=fnt(38, bold=True, mono=False), fill=WHT)
    d.text((W//2 - 230, 182), "Tier 3 · Raspberry Pi 5 (8 GB)", font=fnt(24, bold=True, mono=False), fill=ORG)
    d.rectangle([W//2-230, 220, W//2+230, 222], fill=ORG)
    items = [
        "Install Raspberry Pi OS Lite (64-bit) on SD card",
        "Install Ollama and pull CodeLlama 7B model",
        "Clone SHAPE_Core and install Python requirements",
        "Configure config_pi5.yaml with your network settings",
        "Start the SHAPE HTTP API server",
        "Run Notebook 01 against the live Pi 5 agent",
    ]
    for i, item in enumerate(items):
        d.text((W//2 - 230, 240 + i*34), f"  {i+1}.", font=fnt(17, bold=True), fill=ORG)
        d.text((W//2 - 203, 240 + i*34), item, font=fnt(17, mono=False), fill=WHT)
    frames.append((img, 4))

    # ── Slide 2: OS + Ollama ──────────────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Pi 5 — OS Install + Ollama", ORG, 1, 6)
    footer(d, "Tier 3 · Step 1 of 6")
    section_title(d, 70, "Install OS, then Ollama", ORG)
    term_block(d, 32, 110, 760, 300, [
        "# Flash Raspberry Pi OS Lite 64-bit (same as Tier 2)",
        "# Set hostname: shape-pi5",
        "# Assign static IP in router (e.g. 192.168.1.100)",
        "",
        "$ ssh pi@shape-pi5.local",
        "",
        "# Install Ollama (one command):",
        "$ curl -fsSL https://ollama.com/install.sh | sh",
        ">>> Installing ollama to /usr/local",
        ">>> Creating ollama systemd service...",
        ">>> The Ollama API is now available at 127.0.0.1:11434",
        "✓ Ollama installed",
        "",
        "# Start Ollama service:",
        "$ sudo systemctl enable ollama",
        "$ sudo systemctl start ollama",
        "",
        "# Pull CodeLlama 7B (3.8 GB — takes ~15 min on Pi 5):",
        "$ ollama pull codellama",
        "pulling manifest...",
        "✓ codellama pulled (3.8 GB, q4_K_M quantization)",
    ], title="ssh pi@shape-pi5.local")
    callout_box(d, 820, 110, 420, [
        "Pi 5 requirements:",
        "  8 GB RAM (4 GB works for 7B)",
        "  16 GB+ SD card",
        "  Active cooling recommended",
        "  (CodeLlama runs hot)",
        "",
        "Model options:",
        "  codellama (7B, 3.8 GB) ← default",
        "  codellama:13b (8 GB)   ← Pi5 only",
        "",
        "Verify Ollama is running:",
        "  curl localhost:11434",
        "  → Ollama is running",
    ], ORG)
    frames.append((img, 8))

    # ── Slide 3: Clone + install ──────────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Pi 5 — Clone SHAPE + Install Requirements", ORG, 2, 6)
    footer(d, "Tier 3 · Step 2 of 6")
    section_title(d, 70, "Clone SHAPE_Core + Install Python Requirements", ORG)
    term_block(d, 32, 110, 760, 300, [
        "$ ssh pi@shape-pi5.local",
        "",
        "# Clone the repo:",
        "$ git clone https://github.com/mrivassnj-svg/SHAPE_Core.git",
        "$ cd SHAPE_Core",
        "",
        "# Install Python requirements:",
        "$ pip3 install -r requirements.txt",
        "",
        "# Pin langchain-ollama to avoid HTTP 400 tools error:",
        "$ pip3 install 'langchain-ollama==0.1.3' --force-reinstall",
        "",
        "# Verify the shape package imports cleanly:",
        "$ python3 -c 'from shape.agent import build_agent; print(\"OK\")'",
        "OK",
        "",
        "# Run the unit tests:",
        "$ python3 -m pip install pytest",
        "$ python3 -m pytest tests/ -q",
        "32 passed in 1.9s",
        "✓ All 32 tests pass",
    ], title="ssh pi@shape-pi5.local")
    frames.append((img, 8))

    # ── Slide 4: Config ───────────────────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Pi 5 — Configure config_pi5.yaml", ORG, 3, 6)
    footer(d, "Tier 3 · Step 3 of 6")
    section_title(d, 70, "Edit hardware/pi5/config_pi5.yaml", ORG)
    code_block(d, 32, 110, 580, 380, [
        "# hardware/pi5/config_pi5.yaml",
        "# Edit these values for your setup:",
        "",
        "# LLM",
        "model: codellama",
        "ollama_url: http://localhost:11434",
        "temperature: 0.2",
        "context_window: 4096",
        "",
        "# Agent",
        "memory_window: 6",
        "max_iterations: 8",
        "verbose: false",
        "",
        "# API server",
        "api_host: 0.0.0.0",
        "api_port: 8765",
        "api_key: shape_local_key",
        "",
        "# Paths",
        "feedback_path: data/feedback.jsonl",
        "workspace_dir: workspace",
        "doc_index_path: data/doc_index",
        "",
        "# Whisper voice (optional)",
        "# WHISPER_BIN=/home/pi/whisper.cpp/main",
        "# WHISPER_MODEL=.../ggml-tiny.en.bin",
    ], title="hardware/pi5/config_pi5.yaml")
    callout_box(d, 650, 110, 590, [
        "api_key must match SHAPE_API_KEY",
        "environment variable on Zero 2 W.",
        "",
        "api_host: 0.0.0.0 means the server",
        "listens on ALL interfaces — both",
        "localhost and Wi-Fi.",
        "",
        "api_port: 8765 is the default.",
        "Make sure your router/firewall",
        "allows this port on the LAN.",
        "",
        "verbose: false for production.",
        "Set to true to debug ReAct steps.",
    ], YEL)
    frames.append((img, 7))

    # ── Slide 5: Start API server ─────────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Pi 5 — Start SHAPE API Server", ORG, 4, 6)
    footer(d, "Tier 3 · Step 4 of 6")
    section_title(d, 70, "Start the SHAPE HTTP API Server", ORG)
    term_block(d, 32, 110, 760, 280, [
        "$ cd ~/SHAPE_Core",
        "",
        "# Start the API server:",
        "$ python3 hardware/pi5/api_server.py \\",
        "    --config hardware/pi5/config_pi5.yaml",
        "",
        "2026-11-27 16:00:01  INFO  Loading SHAPE agent (model=codellama)…",
        "2026-11-27 16:00:08  INFO  Agent ready.",
        "2026-11-27 16:00:08  INFO  SHAPE API listening on http://0.0.0.0:8765",
        "2026-11-27 16:00:08  INFO  Press Ctrl+C to stop.",
        "",
        "# Test from the same Pi 5:",
        "$ curl -s -X POST http://localhost:8765/query \\",
        "    -H 'X-API-Key: shape_local_key' \\",
        "    -H 'Content-Type: application/json' \\",
        "    -d '{\"input\": \"print hello world in Python\"}' | python3 -m json.tool",
        "{",
        "    \"output\": \"print('hello world')\"",
        "}",
        "✓ API server responding",
    ], title="ssh pi@shape-pi5.local")
    callout_box(d, 820, 110, 420, [
        "API endpoints:",
        "  POST /query     → agent.run()",
        "  POST /feedback  → RL score",
        "  GET  /status    → model + RL",
        "  POST /reset     → clear memory",
        "  POST /sensor    → auto-alert",
        "  POST /transcribe → whisper",
        "",
        "To run on boot:",
        "$ crontab -e",
        "@reboot sleep 15 && cd ~/SHAPE_Core",
        "&& python3 hardware/pi5/api_server.py",
        "--config hardware/pi5/config_pi5.yaml",
    ], GRN)
    frames.append((img, 8))

    # ── Slide 6: Run Notebook 01 ──────────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Pi 5 — Run Notebook 01 Against Live Agent", ORG, 5, 6)
    footer(d, "Tier 3 · Step 5 of 6")
    section_title(d, 70, "Connect Notebook 01 to the Live Pi 5 Agent", ORG)
    term_block(d, 32, 110, 760, 220, [
        "# Option A: Run Jupyter on the Pi 5 itself",
        "$ pip3 install jupyter",
        "$ jupyter notebook --ip=0.0.0.0 --no-browser",
        "# Open on your laptop: http://shape-pi5.local:8888",
        "",
        "# Option B: Run on your laptop, point at Pi 5 Ollama",
        "# In 01_SHAPE_Introduction.ipynb, change ollama_url:",
        "# 'ollama_url': 'http://192.168.1.100:11434'",
        "",
        "# Option C: Colab (uses Colab's local Ollama install)",
        "# Upload 01_SHAPE_Introduction.ipynb to Colab",
        "# Run setup cells — Ollama installs in the Colab VM",
        "",
        "✓ Notebook 01 runs — test suite passes, agent loads",
    ], title="ssh pi@shape-pi5.local  or  your laptop")
    callout_box(d, 820, 110, 420, [
        "Notebook 01 setup cell:",
        "  git clone + pip install",
        "  + langchain-ollama==0.1.3 pin",
        "",
        "What it proves:",
        "  32 unit tests pass",
        "  Agent loads from shape/",
        "  UART CSV protocol verified",
        "  Sensor alert thresholds work",
        "  ReAct parser all 3 branches",
        "",
        "Total NB01 runtime: ~8 min",
        "(mostly Ollama model load)",
    ], ORG)
    frames.append((img, 7))

    # ── Slide 7: Full system verify ───────────────────────────────────────────
    img, d = slide()
    header(d, 3, "Pi 5 — Full System Verification", ORG, 6, 6)
    footer(d, "All three tiers operational")
    section_title(d, 70, "Full Three-Tier System Verification", GRN)
    checklist(d, 60, 115, [
        (True, "Pi 5: Ollama running on port 11434 with codellama"),
        (True, "Pi 5: api_server.py listening on port 8765"),
        (True, "Pi 5: 32 unit tests pass (pytest tests/)"),
        (True, "Zero 2 W: main_zero2w.py connected to Pi 5"),
        (True, "Zero 2 W: Pi 5 online: True in logs"),
        (True, "Pico 2: UART CSV transmitting every 2 s"),
        (True, "Pico 2 → Zero 2 W → Pi 5 alert cycle works"),
        (True, "Notebook 01 runs end-to-end against live agent"),
    ])
    # Architecture summary at bottom
    d.rectangle([40, 450, W-40, 480], fill=PANEL)
    d.text((60, 457), "Pico 2  →UART→  Zero 2 W  →HTTP→  Pi 5  →Ollama→  CodeLlama 7B", font=fnt(16, bold=True), fill=WHT)
    d.text((60, 490), "GPIO wiring  +  pyserial  +  requests  +  langchain-ollama  +  shape/", font=fnt(14), fill=GRY)
    frames.append((img, 6))

    return frames


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    videos = [
        ("Tier 1 — Pico 2",        tier1_frames, "setup_tier1_pico2.mp4",  CYAN),
        ("Tier 2 — Zero 2 W",      tier2_frames, "setup_tier2_zero2w.mp4", PINK),
        ("Tier 3 — Pi 5 + Agent",  tier3_frames, "setup_tier3_pi5.mp4",    ORG),
    ]

    for title, frames_fn, filename, color in videos:
        print(f"\n{'='*60}")
        print(f"  Rendering: {title}")
        print(f"{'='*60}")
        frames = frames_fn()
        prefix = filename.replace(".mp4", "")
        pairs  = save_frames(frames, prefix)
        out    = OUT / filename
        assemble(pairs, out)

    print(f"\n{'='*60}")
    print("  All setup videos complete:")
    for _, _, fn, _ in videos:
        p = OUT / fn
        s = p.stat().st_size / 1_048_576
        print(f"    {fn}  ({s:.1f} MB)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
