"""
render_slides.py — Fast video builder (no moviepy, no Blender)
Renders slides to PNG with Pillow, assembles MP4 with ffmpeg concat.
Total time: ~5 seconds.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_video import SLIDES

OUT_DIR = Path(__file__).resolve().parent / "output"
SLIDES_DIR = OUT_DIR / "slides"
MP4 = OUT_DIR / "FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4"

SLIDES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Render each slide to PNG
print("Rendering slides to PNG...")
for i, (fn, dur) in enumerate(SLIDES):
    img = fn()
    path = SLIDES_DIR / f"slide_{i:02d}.png"
    img.save(path)
    print(f"  {i+1:2d}/{len(SLIDES)}  {fn.__name__:<30}  {dur}s  → {path.name}")

# 2. Write ffmpeg concat file
concat = SLIDES_DIR / "concat.txt"
with open(concat, "w") as f:
    for i, (_, dur) in enumerate(SLIDES):
        f.write(f"file 'slide_{i:02d}.png'\n")
        f.write(f"duration {dur}\n")

# 3. Assemble MP4
print("\nAssembling MP4 with ffmpeg...")
result = subprocess.run(
    [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat),
        "-vf", "fps=30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(MP4),
    ],
    capture_output=True, text=True,
)

if result.returncode == 0:
    size_mb = MP4.stat().st_size / 1_048_576
    total_s = sum(d for _, d in SLIDES)
    print(f"\n✅  {MP4.name}")
    print(f"   Duration : {total_s//60}m {total_s%60}s")
    print(f"   Size     : {size_mb:.1f} MB")
    print(f"   Slides   : {len(SLIDES)}")
else:
    print("ffmpeg error:")
    print(result.stderr[-600:])
    sys.exit(1)
