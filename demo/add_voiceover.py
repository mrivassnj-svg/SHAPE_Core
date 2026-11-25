"""
add_voiceover.py — Generate TTS narration and merge with demo MP4.

Usage:
    python demo/add_voiceover.py

Output:
    demo/output/FN_Demo_MichaelRivas_Group3_ITAI2376_14562_voiced.mp4

Requirements:
    pip install pyttsx3 pydub
    sudo apt install espeak-ng ffmpeg -y

Group 3 — ITAI2376-14562
Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pyttsx3
from pydub import AudioSegment

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEMO_DIR  = Path(__file__).resolve().parent
OUT_DIR   = DEMO_DIR / "output"
VIDEO_IN  = OUT_DIR / "FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4"
AUDIO_OUT = OUT_DIR / "narration.mp3"
VIDEO_OUT = OUT_DIR / "FN_Demo_MichaelRivas_Group3_ITAI2376_14562_voiced.mp4"

# ---------------------------------------------------------------------------
# Narration segments — (text, duration_seconds)
# Must match SLIDES manifest in make_video.py exactly.
# Empty string = silence for that slide.
# ---------------------------------------------------------------------------
SEGMENTS = [
    # Slide 00 — Opening credits (12s)
    ("", 12),

    # Slide 01 — What is SHAPE? (30s)
    (
        "SHAPE is the Self-Healing Autonomous Programming Engine. "
        "An AI coding agent that runs entirely offline on a Raspberry Pi 5. "
        "No internet connection. No API keys. No monthly subscription. "
        "Just an eighty dollar computer in your pocket, powered by CodeLlama running through Ollama. "
        "SHAPE uses the ReAct reasoning pattern — Thought, Action, Observation — "
        "to plan and execute coding tasks step by step.",
        30,
    ),

    # Slide 02 — Raspberry Pi 5 hardware (20s)
    (
        "Our target device is the Raspberry Pi 5 with eight gigabytes of RAM. "
        "It runs full 64-bit Linux on a BCM2712 processor. "
        "Powered by a USB-C battery bank, it can operate all day in the field. "
        "SHAPE turns this eighty dollar computer into a fully capable AI coding assistant.",
        20,
    ),

    # Slide 03 — Three-tier architecture (25s)
    (
        "SHAPE uses a three-tier offline architecture. "
        "The Pico 2 reads sensor data and sends it over UART to the Zero 2 W. "
        "The Zero 2 W relays requests over Wi-Fi to the Pi 5, "
        "which runs the full SHAPE agent with CodeLlama 7B through Ollama. "
        "All three tiers operate completely offline.",
        25,
    ),

    # Slide 04 — The Problem (28s)
    (
        "The problem with every existing AI coding tool is simple: they all need the cloud. "
        "GitHub Copilot. ChatGPT. Azure OpenAI. All of them fail the moment you lose signal. "
        "Think about a wildfire mapping crew writing sensor scripts in a canyon. "
        "Or a naval engineer in a secure air-gapped compartment. "
        "Or a field researcher at a remote Antarctic station. "
        "These are real scenarios where today's tools are completely unavailable.",
        28,
    ),

    # Slide 05 — Cost comparison (20s)
    (
        "The cost comparison is stark. "
        "GitHub Copilot costs ten dollars a month. ChatGPT Plus costs twenty. "
        "Azure OpenAI can cost sixty dollars or more per month. "
        "SHAPE costs zero dollars per month, forever. "
        "The only cost is the eighty dollar Raspberry Pi 5 hardware.",
        20,
    ),

    # Slide 06 — Live sensor data (25s)
    (
        "Here SHAPE is working with real fieldwork sensor data. "
        "We have loaded a CSV of readings — temperature, humidity, and CO2. "
        "Watch as the CO2 reading hits four hundred thirty-eight parts per million. "
        "SHAPE detects the alert automatically and triggers an action. "
        "This is the kind of real-world integration the agent was built for.",
        25,
    ),

    # Slide 07 — Terminal live demo (50s)
    (
        "Here is SHAPE running live in the terminal. "
        "The user asks: write a palindrome checker, then test it. "
        "Watch the ReAct loop in action. "
        "SHAPE thinks: lint first, then run. "
        "It calls the linter — no issues found. "
        "Then it calls the code executor. "
        "SHAPE writes the function, adds assertions, and runs them. "
        "All tests pass. "
        "Now we give it broken code — a classic type error. "
        "SHAPE lints it, finds the bug, corrects it, and runs again. "
        "This is what Self-Healing means: "
        "SHAPE does not just generate code — it validates and fixes it in a closed loop.",
        50,
    ),

    # Slide 08 — All tests passed (10s)
    (
        "All tests passed. Self-healing complete.",
        10,
    ),

    # Slide 09 — Code overview (30s)
    (
        "The codebase has five core modules. "
        "agent dot py wires together LangChain, Ollama, and four tools "
        "inside a ReAct executor with sliding-window conversation memory. "
        "safety dot py screens every request before it reaches the model, "
        "blocking harmful commands and out-of-scope requests. "
        "feedback dot py is our reinforcement learning component. "
        "After each response, the user rates it one to five stars. "
        "A rolling average generates a policy hint that improves future responses.",
        30,
    ),

    # Slide 10 — The pitch (30s)
    (
        "SHAPE proves that powerful AI assistance does not require the cloud. "
        "An eighty dollar device, an open-source model, and a thoughtful architecture "
        "is all it takes to put a capable coding agent anywhere on the planet. "
        "For researchers, engineers, students, and developers who work at the edge — "
        "SHAPE is the tool that goes with them. "
        "Offline. Intelligent. Yours.",
        30,
    ),

    # Slide 11 — Closing credits (20s)
    (
        "This is Group Three. Thank you.",
        20,
    ),
]

# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def make_engine() -> pyttsx3.Engine:
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1.0)
    return engine


def synthesise(engine: pyttsx3.Engine, text: str,
               duration_s: float, tmp_dir: str) -> AudioSegment:
    target_ms = int(duration_s * 1000)
    if not text.strip():
        return AudioSegment.silent(duration=target_ms)

    wav_path = os.path.join(tmp_dir, "seg.wav")
    engine.save_to_file(text, wav_path)
    engine.runAndWait()

    seg = AudioSegment.from_wav(wav_path)
    if len(seg) < target_ms:
        seg = seg + AudioSegment.silent(duration=target_ms - len(seg))
    else:
        seg = seg[:target_ms]
    return seg.set_frame_rate(44100).set_channels(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("SHAPE Voiceover Generator")
    print("=" * 40)
    total_s = sum(d for _, d in SEGMENTS)
    print(f"Segments : {len(SEGMENTS)}  |  Duration : {total_s // 60}m {total_s % 60}s\n")

    engine  = make_engine()
    combined = AudioSegment.empty()

    with tempfile.TemporaryDirectory() as tmp:
        for i, (text, dur) in enumerate(SEGMENTS):
            label = (text[:55] + "...") if text else "(silence)"
            print(f"  [{i+1:2d}/{len(SEGMENTS)}]  {dur:3d}s  {label}")
            combined += synthesise(engine, text, dur, tmp)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nExporting audio → {AUDIO_OUT.name}")
    combined.export(str(AUDIO_OUT), format="mp3", bitrate="128k")

    print(f"Merging with video → {VIDEO_OUT.name}")
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(VIDEO_IN),
        "-i", str(AUDIO_OUT),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
        str(VIDEO_OUT),
    ], capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = VIDEO_OUT.stat().st_size / 1_048_576
        print(f"\n✅  {VIDEO_OUT.name}  ({size_mb:.1f} MB)")
        print(f"\nSubmit this file:\n  {VIDEO_OUT}")
    else:
        print("ffmpeg error:"); print(result.stderr[-600:])


if __name__ == "__main__":
    main()
