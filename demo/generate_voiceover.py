"""
generate_voiceover.py — Converts narration_script.txt into per-clip WAV files
=============================================================================
Reads narration_script.txt, extracts the voice lines for each clip,
and generates a WAV audio file for every CLIP_* block using gTTS (Google TTS,
free, works online) or pyttsx3 (fully offline fallback).

The output WAVs are named voice_CLIP_*.wav and placed in demo/assets/ —
exactly the filenames render_demo.py expects.

Usage:
  pip install gtts pydub pyttsx3
  python demo/generate_voiceover.py

  # Offline-only (no internet):
  python demo/generate_voiceover.py --offline

Group 3 — ITAI2376-14562
Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NARRATION_SCRIPT = REPO_ROOT / "demo" / "narration_script.txt"
ASSETS_DIR = REPO_ROOT / "demo" / "assets"

# ---------------------------------------------------------------------------
# Timing data — must match render_demo.py CLIP_MANIFEST
# ---------------------------------------------------------------------------
CLIP_TIMING = {
    "CLIP_CREDITS":    (0,   12),
    "CLIP_INTRO":      (12,  60),
    "CLIP_WHY":        (60,  115),
    "CLIP_DEVICE":     (115, 150),
    "CLIP_LIVE_DEMO":  (150, 210),
    "CLIP_CODE":       (210, 250),
    "CLIP_PITCH":      (250, 290),
    "CLIP_END":        (290, 300),
}


# ---------------------------------------------------------------------------
# Parse narration script → {clip_id: voice_lines}
# ---------------------------------------------------------------------------

def parse_narration(path: Path) -> dict[str, str]:
    """
    Extract the Voice: text for each CLIP_* block.
    Returns {clip_id: narration_text}.
    """
    text = path.read_text(encoding="utf-8")
    clips: dict[str, str] = {}

    # Find all CUE blocks
    cue_pattern = re.compile(
        r"\[CUE\s+[\d:]+\s*[–-]\s*[\d:]+\]\s+(\w+).*?Voice:(.*?)(?=\[CUE|\Z)",
        re.DOTALL,
    )
    for match in cue_pattern.finditer(text):
        clip_id = match.group(1).strip()
        raw_voice = match.group(2).strip()

        # Strip comment lines (starting with #) and quote marks
        lines = []
        for line in raw_voice.splitlines():
            stripped = line.strip().strip('"')
            if stripped and not stripped.startswith("#") and stripped != "(none — soft ambient music only)" and stripped != "(none — music fades out)":
                lines.append(stripped)

        voice_text = " ".join(lines)
        if voice_text:
            clips[clip_id] = voice_text

    return clips


# ---------------------------------------------------------------------------
# TTS backends
# ---------------------------------------------------------------------------

def tts_gtts(text: str, output_wav: Path) -> None:
    """Generate speech using gTTS (requires internet). Saves as WAV via pydub."""
    from gtts import gTTS
    from pydub import AudioSegment

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_mp3 = Path(tmp.name)

    gTTS(text=text, lang="en", slow=False).save(str(tmp_mp3))
    AudioSegment.from_mp3(str(tmp_mp3)).export(str(output_wav), format="wav")
    tmp_mp3.unlink(missing_ok=True)


def tts_pyttsx3(text: str, output_wav: Path) -> None:
    """Generate speech using pyttsx3 (fully offline). Saves directly to WAV."""
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", 160)   # slightly slower for clarity
    engine.setProperty("volume", 1.0)
    engine.save_to_file(text, str(output_wav))
    engine.runAndWait()


# ---------------------------------------------------------------------------
# Pad / trim audio to match clip duration
# ---------------------------------------------------------------------------

def fit_to_duration(wav_path: Path, target_seconds: int) -> None:
    """
    Trim or pad the WAV file so its duration matches target_seconds exactly.
    - If voice is longer: truncate to target (rarely happens for these scripts).
    - If voice is shorter: pad with silence at the end.
    This ensures audio and video strips stay in sync in Blender.
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_wav(str(wav_path))
        target_ms = target_seconds * 1000
        current_ms = len(audio)

        if current_ms < target_ms:
            silence = AudioSegment.silent(duration=(target_ms - current_ms))
            audio = audio + silence
        elif current_ms > target_ms:
            audio = audio[:target_ms]

        audio.export(str(wav_path), format="wav")
    except ImportError:
        print("  [WARN] pydub not installed — skipping duration fit. pip install pydub")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(offline: bool = False) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if not NARRATION_SCRIPT.exists():
        print(f"[ERROR] Narration script not found: {NARRATION_SCRIPT}")
        return

    clips = parse_narration(NARRATION_SCRIPT)
    print(f"Parsed {len(clips)} clips with voice lines.\n")

    tts_fn = tts_pyttsx3 if offline else tts_gtts
    backend_name = "pyttsx3 (offline)" if offline else "gTTS (online)"
    print(f"Using TTS backend: {backend_name}\n")

    for clip_id, timing in CLIP_TIMING.items():
        start_s, end_s = timing
        duration_s = end_s - start_s
        out_wav = ASSETS_DIR / f"voice_{clip_id}.wav"

        voice_text = clips.get(clip_id, "")

        if not voice_text:
            # Silent placeholder (opening/closing credits)
            print(f"  [{clip_id}] No voice — writing {duration_s}s silence.")
            try:
                from pydub import AudioSegment
                silence = AudioSegment.silent(duration=duration_s * 1000)
                silence.export(str(out_wav), format="wav")
            except ImportError:
                # Fallback: write minimal valid WAV header manually
                _write_silent_wav(out_wav, duration_s)
            continue

        print(f"  [{clip_id}] Generating {duration_s}s voice → {out_wav.name}")
        print(f"    Text: {voice_text[:80]}{'...' if len(voice_text) > 80 else ''}")

        try:
            tts_fn(voice_text, out_wav)
            fit_to_duration(out_wav, duration_s)
            print(f"    ✅ Saved ({out_wav.stat().st_size // 1024} KB)")
        except Exception as exc:  # noqa: BLE001
            print(f"    ⚠  TTS failed: {exc}")
            _write_silent_wav(out_wav, duration_s)

    print(f"\nAll voice files saved to: {ASSETS_DIR}")
    print("Next step: run  blender --background --python demo/render_demo.py")


def _write_silent_wav(path: Path, duration_s: int) -> None:
    """Write a minimal valid WAV file containing silence."""
    import struct
    sample_rate = 44100
    num_samples = sample_rate * duration_s
    data_size = num_samples * 2  # 16-bit mono

    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate SHAPE demo voiceover WAVs.")
    parser.add_argument(
        "--offline", action="store_true",
        help="Use pyttsx3 (offline) instead of gTTS (online)"
    )
    args = parser.parse_args()
    main(offline=args.offline)
