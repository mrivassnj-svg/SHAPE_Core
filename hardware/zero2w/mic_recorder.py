"""
mic_recorder.py — Record a short WAV clip from a USB or I2S mic on the Zero 2 W.

Supported hardware:
  USB mic  → plug into Zero 2 W via micro-USB OTG adapter; device usually hw:1,0
  INMP441  → I2S wiring: SCK=GPIO18, WS=GPIO19, SD=GPIO20; device hw:0,0

Install dependency:  sudo apt-get install -y alsa-utils
"""

import subprocess
import tempfile
import pathlib
import logging

log = logging.getLogger("mic_recorder")

# Default ALSA device — USB mic is typically hw:1,0 on Zero 2 W
# Override with MIC_DEVICE env var if yours is different
import os
DEFAULT_DEVICE = os.getenv("MIC_DEVICE", "hw:1,0")
SAMPLE_RATE    = 16000   # Whisper expects 16 kHz
CHANNELS       = 1
FORMAT         = "S16_LE"


def record_wav(seconds: int = 5, device: str = DEFAULT_DEVICE) -> pathlib.Path:
    """
    Record `seconds` of audio and return the path to a temporary WAV file.
    Caller is responsible for deleting the file when done.
    Raises subprocess.CalledProcessError if arecord fails.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out_path = pathlib.Path(tmp.name)

    cmd = [
        "arecord",
        "-D", device,
        "-f", FORMAT,
        "-r", str(SAMPLE_RATE),
        "-c", str(CHANNELS),
        "-d", str(seconds),
        str(out_path),
    ]
    log.info("Recording %ds from %s → %s", seconds, device, out_path)
    subprocess.run(cmd, check=True, capture_output=True)
    log.info("Recording done: %.1f KB", out_path.stat().st_size / 1024)
    return out_path


def list_devices() -> str:
    """Return arecord -l output so the user can find their mic device string."""
    result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
    return result.stdout


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Available recording devices:\n", list_devices())
    p = record_wav(3)
    print(f"Saved to {p}  ({p.stat().st_size} bytes)")
