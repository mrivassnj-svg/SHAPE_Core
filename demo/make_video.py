"""
make_video.py — SHAPE Demo Video Generator
==========================================
Pure Python. No Blender. No 3D rendering.
Generates the full 5-minute demo video in ~60 seconds.

Each "slide" is a Pillow image. moviepy stitches them into an MP4.

Usage:
    python demo/make_video.py

Output:
    demo/output/FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4

Group 3 — ITAI2376-14562
Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    import numpy as np
    from moviepy import ImageClip, concatenate_videoclips
    _MOVIEPY = True
except ImportError:
    _MOVIEPY = False

# ---------------------------------------------------------------------------
# Canvas settings
# ---------------------------------------------------------------------------
W, H   = 1280, 720
FPS    = 30
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

OUTPUT = Path(__file__).resolve().parent / "output" / \
         "FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4"

# ---------------------------------------------------------------------------
# Anime palette  (R, G, B)
# ---------------------------------------------------------------------------
BG    = ( 10,   8,  26)   # deep violet
INK   = (  5,   5,  10)
BLUE  = ( 25, 140, 255)
PINK  = (255,  46, 140)
YEL   = (255, 224,   0)
GRN   = ( 20, 255, 115)
ORG   = (255, 115,   0)
WHT   = (255, 255, 255)
GRY   = (153, 153, 179)
TEAL  = (  0, 242, 230)
RED   = (255,  25,  25)
PCB   = ( 13, 102,  38)

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    path = BOLD_PATH if bold else FONT_PATH
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------

def new_slide() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    return img, d


def rect(d: ImageDraw.ImageDraw, x1, y1, x2, y2,
         fill, outline=None, width=4):
    d.rectangle([x1, y1, x2, y2], fill=fill,
                outline=outline or fill, width=width)


def text(d: ImageDraw.ImageDraw, txt: str, x, y, color=WHT,
         size=28, bold=False, anchor="mm"):
    d.text((x, y), txt, font=font(size, bold), fill=color, anchor=anchor)


def subtitle_bar(d: ImageDraw.ImageDraw, line: str):
    """Black subtitle bar at bottom with white text."""
    rect(d, 0, H - 54, W, H, (0, 0, 0))
    if line:
        text(d, line, W // 2, H - 27, WHT, size=22)


def header_bar(d: ImageDraw.ImageDraw, title: str, color=BLUE):
    rect(d, 0, 0, W, 70, color)
    text(d, title, W // 2, 35, INK, size=30, bold=True)


def pill(d: ImageDraw.ImageDraw, x, y, w, h, fill, border, label="", lcolor=WHT, lsize=22):
    rect(d, x - w//2 - 5, y - h//2 - 5,
             x + w//2 + 5, y + h//2 + 5, border, border, 0)
    rect(d, x - w//2, y - h//2, x + w//2, y + h//2, fill, fill, 0)
    if label:
        text(d, label, x, y, lcolor, lsize, anchor="mm")


# ---------------------------------------------------------------------------
# Slide builders — one function per act / section
# ---------------------------------------------------------------------------

def slide_credits() -> Image.Image:
    img, d = new_slide()
    # Big title box
    rect(d,  90, 160, W-90, 390, (20, 10, 55), BLUE, 5)
    text(d, "SHAPE", W//2, 240, YEL,  size=96, bold=True, anchor="mm")
    text(d, "Self-Healing Autonomous Programming Engine",
         W//2, 325, TEAL, size=26, anchor="mm")
    # Credits
    text(d, "Group 3  |  ITAI2376-14562",         W//2, 430, WHT,  size=24, anchor="mm")
    text(d, "Cherluk Sumdin  ·  Olubukola Kukoyi", W//2, 475, GRY,  size=20, anchor="mm")
    text(d, "Taki Eddine Boubekri  ·  Michael Rivas", W//2, 510, GRY, size=20, anchor="mm")
    subtitle_bar(d, "SHAPE — Self-Healing Autonomous Programming Engine")
    return img


def slide_what_is_shape() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "What is SHAPE?", BLUE)
    rows = [
        ("Offline AI coding agent",           "No internet. No API key. No cost.", TEAL),
        ("Runs on Raspberry Pi 5",            "80 USD device — fits in your pocket.", GRN),
        ("LLM: CodeLlama 7B via Ollama",      "Open-source, fully local.",           YEL),
        ("LangChain ReAct reasoning",         "Thought → Action → Observation loop.", PINK),
        ("RL feedback loop",                  "1–5 star ratings adjust prompt strategy.", ORG),
    ]
    for i, (title, desc, col) in enumerate(rows):
        y = 150 + i * 108
        rect(d, 60, y, W-60, y+88, (20, 15, 50), col, 3)
        text(d, title, 120, y+28, col,  size=24, bold=True, anchor="lm")
        text(d, desc,  120, y+62, GRY,  size=20, anchor="lm")
    subtitle_bar(d, "An offline AI coding agent running on Raspberry Pi 5")
    return img


def slide_pi_board() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "Raspberry Pi 5 — The Hardware", GRN)
    # PCB
    rect(d, 180, 100, W-180, 580, PCB, GRN, 6)
    # Components
    chips = [
        (460, 310, 160, 130, (20,20,20), TEAL,  "BCM2712 SoC"),
        (680, 260,  90,  90, (20,20,20), PINK,  "8 GB RAM"),
        (460, 170, 480,  36, (30,30,30), YEL,   "GPIO × 40"),
        (220, 290,  55,  90, (100,100,110), WHT, "USB-A"),
        (220, 390,  55,  90, (100,100,110), WHT, "USB-A"),
        (220, 480,  50,  70, (100,100,110), BLUE,"USB-C"),
        (380, 540,  90,  40, (100,100,110), WHT, "HDMI"),
        (760, 170, 110,  36, (100,100,110), GRY, "microSD"),
    ]
    for cx, cy, cw, ch, cf, cb, cl in chips:
        pill(d, cx, cy, cw, ch, cf, cb, cl, cb, 18)
    # LEDs
    d.ellipse([218, 530, 242, 554], fill=RED,   outline=RED)
    d.ellipse([218, 558, 242, 582], fill=GRN,   outline=GRN)
    # Badge
    rect(d, 180, 598, W-180, 648, INK, BLUE, 4)
    text(d, "85 × 56 mm  —  fits in a shirt pocket  —  $80 USD",
         W//2, 623, TEAL, size=22, bold=True, anchor="mm")
    subtitle_bar(d, "Runs entirely offline — no internet required")
    return img


def slide_arch_diagram() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "SHAPE — Software Architecture", YEL)
    # Vertical flow: InputGuard → ReAct Agent → RL Feedback
    boxes = [
        (W//2, 165, "InputGuard",          "Pre-LLM safety screen\nregex, < 1 ms",          PINK,  PINK),
        (W//2, 320, "ReAct Agent",         "Thought → Action → Observation\nmax 8 iterations", BLUE,  TEAL),
        (W//2, 475, "FeedbackMemory",      "1–5 star ratings\nadjust system prompt",           GRN,   GRN),
    ]
    for bx, by, title, desc, fill, bord in boxes:
        pill(d, bx, by, 340, 100, (20, 15, 50), bord, "", WHT, 20)
        text(d, title, bx, by - 18, fill,  size=22, bold=True, anchor="mm")
        for j, ln in enumerate(desc.split("\n")):
            text(d, ln, bx, by + 10 + j * 22, GRY, size=18, anchor="mm")
    # Arrows between boxes
    for y1, y2 in [(215, 270), (370, 425)]:
        d.line([(W//2, y1), (W//2, y2)], fill=WHT, width=4)
        d.polygon([(W//2-10, y2-2), (W//2+10, y2-2), (W//2, y2+14)], fill=WHT)
    # Tools row
    tools = [("linter", YEL), ("code_executor", ORG), ("file_manager", TEAL), ("doc_search", PINK)]
    tool_y = 575
    for i, (name, col) in enumerate(tools):
        tx = 160 + i * 250
        pill(d, tx, tool_y, 200, 48, (20, 15, 50), col, name, col, 15)
    # Arrow from agent to tools
    d.line([(W//2, 370), (W//2, tool_y - 24)], fill=WHT, width=2)
    for i, (name, col) in enumerate(tools):
        tx = 160 + i * 250
        d.line([(W//2, tool_y - 24), (tx, tool_y - 24)], fill=WHT, width=2)
        d.line([(tx, tool_y - 24), (tx, tool_y - 24)], fill=WHT, width=2)
    subtitle_bar(d, "InputGuard → ReAct loop → 4 tools → RL feedback")
    return img


def slide_problem() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "The Problem", PINK)
    text(d, "Every AI coding tool requires the cloud.", W//2, 130, WHT, size=28, bold=True, anchor="mm")
    scenarios = [
        ("Wildfire mapping crew",     "No cell signal in the canyon",    ORG),
        ("Naval engineering bay",     "Secure air-gapped compartment",   RED),
        ("Antarctic research station","Satellite latency > 2 seconds",   TEAL),
        ("Hospital network",          "HIPAA air-gap — no cloud allowed", PINK),
        ("School robotics class",     "No Wi-Fi budget",                 YEL),
    ]
    for i, (place, reason, col) in enumerate(scenarios):
        y = 180 + i * 96
        d.ellipse([72, y+18, 102, y+48], fill=col)
        text(d, place,  130, y+22, col, size=22, bold=True, anchor="lm")
        text(d, reason, 130, y+52, GRY, size=19, anchor="lm")
    subtitle_bar(d, "These developers have no AI coding help at all — until now")
    return img


def slide_cost_chart() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "Cost Comparison", GRN)
    tools = [
        ("GitHub\nCopilot", 10, RED,  200),
        ("ChatGPT\nPlus",   20, ORG,  430),
        ("Azure\nOpenAI",   60, PINK, 660),
        ("SHAPE",            0, GRN,  890),
    ]
    max_h = 380
    base_y = 650
    for name, cost, col, bx in tools:
        bar_h = max(8, int((cost / 60) * max_h)) if cost else 8
        rect(d, bx-70, base_y-bar_h, bx+70, base_y, col, INK, 3)
        cost_str = f"${cost}/mo" if cost else "FREE"
        text(d, cost_str, bx, base_y-bar_h-22, WHT if cost else GRN, size=22, bold=True, anchor="mm")
        for j, line in enumerate(name.split("\n")):
            text(d, line, bx, base_y+28+j*26, col, size=20, anchor="mm")
    # Zero line
    d.line([(100, base_y), (W-100, base_y)], fill=WHT, width=3)
    subtitle_bar(d, "SHAPE costs $0 per month — no recurring fees")
    return img


def slide_sensor_stream() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "Fieldwork: Live Sensor Data", TEAL)
    readings = [
        ("timestamp: 2026-11-23 06:00",  WHT),
        ("temp:    22.4 °C",             GRN),
        ("humid:   54.1 %",              TEAL),
        ("CO2:     412 ppm",             GRN),
        ("temp:    23.1 °C",             GRN),
        ("CO2:     431 ppm",             GRN),
        ("CO2:     438 ppm  ⚠  ALERT!", RED),
        ("humid:   58.9 %",              ORG),
        ("→ User asks SHAPE to analyze", YEL),
    ]
    rect(d, 60, 90, W-60, 630, (5, 20, 5), GRN, 3)
    for i, (line, col) in enumerate(readings):
        y = 128 + i * 56
        text(d, line, 100, y, col, size=22, bold=(col==RED or col==YEL), anchor="lm")
    subtitle_bar(d, "Simulated sensor CSV — the kind of data SHAPE processes in the field")
    return img


def slide_terminal() -> Image.Image:
    img, d = new_slide()
    # Terminal window
    rect(d, 20, 20, W-20, H-60, (5, 18, 5), GRN, 4)
    rect(d, 20, 20, W-20, 60,   (0, 60, 20), GRN, 0)
    text(d, "SHAPE Terminal  —  model: codellama  —  Ollama  —  offline",
         W//2, 40, GRN, size=19, anchor="mm")
    lines = [
        ("> SHAPE v1.0 ready",                           GRN),
        ("",                                              GRN),
        ("User:  Write a palindrome checker, then test it.", WHT),
        ("",                                              GRN),
        ("Thought:  lint first, then run.",               BLUE),
        ("Action:   linter",                              YEL),
        ("Obs:      No issues found.          [OK]",      GRN),
        ("Action:   code_executor",                       YEL),
        ("  def is_palindrome(s):",                       TEAL),
        ("      s = s.lower().replace(' ', '')",          TEAL),
        ("      return s == s[::-1]",                     TEAL),
        ("  assert is_palindrome('racecar')",             TEAL),
        ("  assert not is_palindrome('hello')",           TEAL),
        ("Obs:      All tests passed.         [OK]",      GRN),
        ("",                                              GRN),
        ("Final Answer:  Function verified and tested.  ✓", WHT),
    ]
    for i, (line, col) in enumerate(lines):
        text(d, line, 46, 80 + i * 36, col, size=20, bold=(col==WHT and i>1), anchor="lm")
    subtitle_bar(d, "ReAct loop: Thought → Action → Observation → Answer")
    return img


def slide_all_tests_passed() -> Image.Image:
    img, d = new_slide()
    rect(d, 0, 0, W, H, (0, 30, 10))
    rect(d, 80, 220, W-80, 460, (0, 60, 20), GRN, 6)
    text(d, "✓", W//2, 295, GRN, size=100, bold=True, anchor="mm")
    text(d, "All tests passed", W//2, 390, WHT, size=42, bold=True, anchor="mm")
    text(d, "Self-healing complete", W//2, 435, GRN, size=26, anchor="mm")
    subtitle_bar(d, "Self-healing: SHAPE wrote, linted, executed, and verified the code")
    return img


def slide_code_overview() -> Image.Image:
    img, d = new_slide()
    header_bar(d, "SHAPE Codebase — 5 Core Modules", BLUE)
    modules = [
        ("agent.py",    "LangChain ReAct executor over Ollama",     BLUE,  PINK),
        ("feedback.py", "RL reward loop — 1–5 star ratings",        GRN,   TEAL),
        ("safety.py",   "InputGuard — blocks harmful requests",     ORG,   YEL),
        ("tools/ ×4",   "executor · linter · file manager · docs",  TEAL,  BLUE),
    ]
    for i, (name, desc, fill, bord) in enumerate(modules):
        col = i % 2
        row = i // 2
        x1 = 50  + col * 630
        y1 = 100 + row * 240
        rect(d, x1, y1, x1+590, y1+200, fill, bord, 5)
        text(d, name, x1+20, y1+55, WHT,  size=28, bold=True, anchor="lm")
        text(d, desc, x1+20, y1+105, GRY, size=20, anchor="lm")
    subtitle_bar(d, "Clean architecture: guard → reason → act → learn")
    return img


def slide_pitch() -> Image.Image:
    img, d = new_slide()
    # Big gradient-style box
    rect(d, 40, 40, W-40, H-60, (10, 0, 35), BLUE, 6)
    text(d, "SHAPE",                            W//2, 155, YEL,  size=100, bold=True, anchor="mm")
    text(d, "Offline.  Intelligent.  Yours.",   W//2, 255, WHT,  size=36,  bold=True, anchor="mm")
    d.line([(120, 285), (W-120, 285)], fill=BLUE, width=3)
    bullets = [
        ("$80 hardware  ·  $0 / month",              GRN),
        ("Works anywhere on Earth — or off it",       TEAL),
        ("Adapts prompt strategy from your ratings",  TEAL),
        ("100% offline  ·  no data leaves the device", GRY),
    ]
    for i, (line, col) in enumerate(bullets):
        text(d, line, W//2, 340 + i * 68, col, size=26, anchor="mm")
    subtitle_bar(d, "$80 hardware. $0/month. Works anywhere on Earth.")
    return img


def slide_credits_end() -> Image.Image:
    img, d = new_slide()
    rect(d, 60, 80, W-60, H-60, INK, BLUE, 6)
    text(d, "Thank you",                             W//2, 185, YEL,  size=72, bold=True, anchor="mm")
    d.line([(160, 230), (W-160, 230)], fill=BLUE, width=3)
    text(d, "Group 3  |  ITAI2376-14562",            W//2, 290, WHT,  size=28, anchor="mm")
    names = ["Cherluk Sumdin", "Olubukola Kukoyi",
             "Taki Eddine Boubekri", "Michael Rivas"]
    for i, name in enumerate(names):
        text(d, name, W//2, 370 + i * 60, TEAL, size=24, anchor="mm")
    text(d, "SHAPE — Self-Healing Autonomous Programming Engine",
         W//2, 610, GRY, size=18, anchor="mm")
    return img


# ---------------------------------------------------------------------------
# Slide manifest  — (slide_fn, duration_seconds)
# ---------------------------------------------------------------------------
SLIDES = [
    (slide_credits,       12),   # 0:00 – 0:12
    (slide_what_is_shape, 30),   # 0:12 – 0:42
    (slide_pi_board,      20),   # 0:42 – 1:02
    (slide_arch_diagram,  25),   # 1:02 – 1:27
    (slide_problem,       28),   # 1:27 – 1:55
    (slide_cost_chart,    20),   # 1:55 – 2:15
    (slide_sensor_stream, 25),   # 2:15 – 2:40
    (slide_terminal,      50),   # 2:40 – 3:30
    (slide_all_tests_passed, 10),# 3:30 – 3:40
    (slide_code_overview, 30),   # 3:40 – 4:10
    (slide_pitch,         30),   # 4:10 – 4:40
    (slide_credits_end,   20),   # 4:40 – 5:00
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_video():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    clips = []
    total = sum(d for _, d in SLIDES)
    elapsed = 0

    for i, (fn, duration) in enumerate(SLIDES):
        print(f"  Slide {i+1:2d}/{len(SLIDES)}  {fn.__name__:<30}  {duration}s")
        img   = fn()
        clip  = ImageClip(np.array(img), duration=duration)
        clips.append(clip)
        elapsed += duration

    print(f"\nTotal: {total}s  ({total//60}m {total%60}s)")
    print("Assembling MP4...")

    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        str(OUTPUT),
        fps=FPS,
        codec="libx264",
        preset="fast",
        ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p"],
        logger=None,
    )
    size_mb = OUTPUT.stat().st_size / 1_048_576
    print(f"\n✅  {OUTPUT}")
    print(f"   Size: {size_mb:.1f} MB  |  Duration: {total}s  |  {len(SLIDES)} slides")


if __name__ == "__main__":
    print("SHAPE Demo Video Generator")
    print("=" * 40)
    build_video()
