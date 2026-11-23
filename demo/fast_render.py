"""
fast_render.py — Smart render wrapper for scene_demo.py
========================================================
Blender renders every frame even when nothing moves.
This script:
  1. Collects every keyframe timestamp from scene_demo's CLIP_MANIFEST
     (sections that are truly static between those keyframes)
  2. Renders ONLY the keyframe frames + 1 frame per static section
  3. Copies/symlinks identical frames for the in-between range
  4. Assembles the final MP4 with ffmpeg using concat demuxer
     (no quality loss from re-encoding statics)

Result: renders ~200 unique frames instead of 9000
        → full video in under 2 minutes instead of 30+

Usage:
    python demo/fast_render.py

    # or with explicit blender path:
    python demo/fast_render.py --blender /usr/bin/blender

Group 3 — ITAI2376-14562
Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config — must stay in sync with scene_demo.py
# ---------------------------------------------------------------------------
FPS          = 30
TOTAL_FRAMES = 300 * FPS   # 9000

REPO_ROOT  = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "demo" / "output"
FRAMES_DIR = OUTPUT_DIR / "frames"
SCENE_SCRIPT = REPO_ROOT / "demo" / "scene_demo.py"
OUTPUT_MP4   = OUTPUT_DIR / "FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4"

# Every point where something new happens (seconds).
# Source of truth: keyframe timestamps in scene_demo.py acts.
# We render one frame at each of these + 1 frame for every inter-keyframe gap.
KEYFRAME_SECONDS = sorted(set([
    # Act 1
    0, 0.5, 2, 11, 12, 14, 20, 28, 30, 31, 32, 40,
    # Act 2
    60, 61, 65.5, 70.5, 75.5, 80.5, 85.5, 85, 86, 110,
    # Act 3
    115, 117, 120, 128, 135, 148,
    # Act 4
    150, 151, 154, 155, 156, 157, 158, 159, 160, 161,
    162, 163, 164, 165, 166, 167, 168, 169, 170, 171,
    172, 173, 180, 202, 207,
    # Act 5
    210, 212, 214.5, 217, 219.5, 250, 254, 257, 260,
    293, 294, 296, 299,
    # Clip boundaries from CLIP_MANIFEST
    0, 12, 60, 115, 150, 210, 250, 290, 299,
]))


def seconds_to_frame(s: float) -> int:
    return max(1, min(TOTAL_FRAMES, round(s * FPS) + 1))


def build_render_plan() -> list[tuple[int, int]]:
    """
    Returns a list of (render_frame, start_frame, end_frame) triples.
    render_frame is rendered by Blender.
    It is then used for every frame in [start_frame, end_frame].
    """
    kf_frames = sorted(set(seconds_to_frame(s) for s in KEYFRAME_SECONDS))

    # Add midpoints between consecutive keyframes to catch mid-section changes
    extra = []
    for a, b in zip(kf_frames, kf_frames[1:]):
        mid = (a + b) // 2
        if mid not in kf_frames and b - a > FPS:   # only if gap > 1 second
            extra.append(mid)
    kf_frames = sorted(set(kf_frames + extra + [1, TOTAL_FRAMES]))

    plan: list[tuple[int, int, int]] = []
    for i, frame in enumerate(kf_frames):
        next_frame = kf_frames[i + 1] if i + 1 < len(kf_frames) else TOTAL_FRAMES + 1
        plan.append((frame, frame, next_frame - 1))

    return plan


def render_frames(blender: str, plan: list[tuple[int, int, int]]) -> None:
    """Render only the unique frames using Blender in frame-jump mode."""
    frames_to_render = [str(rf) for rf, _, _ in plan]
    frame_list = ",".join(frames_to_render)

    print(f"[fast_render] Rendering {len(frames_to_render)} unique frames "
          f"(of {TOTAL_FRAMES} total)...")
    print(f"[fast_render] Estimated time: "
          f"~{len(frames_to_render) * 0.22:.0f} seconds at ~4.5 fps")

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        blender,
        "--factory-startup", "--background",
        "--python", str(SCENE_SCRIPT),
        "-f", frame_list,
    ]

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print("[fast_render] WARNING: Blender exited non-zero — check output above.")


def expand_frames(plan: list[tuple[int, int, int]]) -> None:
    """
    For each rendered frame, copy (or hardlink) it to fill the frame range
    it represents.  This avoids re-rendering identical frames.
    """
    print("[fast_render] Expanding rendered frames to full sequence...")

    total_copied = 0
    for render_frame, start_f, end_f in plan:
        src = FRAMES_DIR / f"frame_{render_frame:04d}.png"
        if not src.exists():
            print(f"  [WARN] Missing rendered frame: {src.name}")
            continue
        for f in range(start_f, end_f + 1):
            if f == render_frame:
                continue
            dst = FRAMES_DIR / f"frame_{f:04d}.png"
            if dst.exists():
                dst.unlink()
            try:
                dst.hardlink_to(src)   # hardlink = no disk space wasted
            except OSError:
                shutil.copy2(src, dst)
            total_copied += 1

    print(f"[fast_render] Expanded {total_copied} frames from {len(plan)} rendered frames.")


def assemble_mp4() -> None:
    """Assemble the PNG sequence into an MP4 using ffmpeg."""
    print("[fast_render] Assembling MP4...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES_DIR / "frame_%04d.png"),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-threads", "0",
        str(OUTPUT_MP4),
    ]
    result = subprocess.run(cmd)
    if result.returncode == 0 and OUTPUT_MP4.exists():
        size_mb = OUTPUT_MP4.stat().st_size / 1_048_576
        print(f"[fast_render] ✅ Done!  {OUTPUT_MP4}")
        print(f"[fast_render]    Size: {size_mb:.1f} MB")
    else:
        print("[fast_render] ❌ ffmpeg failed — check output above.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast render wrapper for SHAPE scene_demo.py"
    )
    parser.add_argument(
        "--blender", default="blender",
        help="Path to blender executable (default: blender in PATH)"
    )
    parser.add_argument(
        "--skip-render", action="store_true",
        help="Skip Blender rendering (use existing frames)"
    )
    parser.add_argument(
        "--skip-expand", action="store_true",
        help="Skip frame expansion (use existing sequence)"
    )
    args = parser.parse_args()

    plan = build_render_plan()
    print(f"[fast_render] Plan: {len(plan)} unique frames cover {TOTAL_FRAMES} total frames")

    if not args.skip_render:
        render_frames(args.blender, plan)

    if not args.skip_expand:
        expand_frames(plan)

    assemble_mp4()


if __name__ == "__main__":
    main()
