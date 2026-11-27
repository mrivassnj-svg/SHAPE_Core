"""
voice_loop.py — Pi 5 voice interaction loop for SHAPE showcase rig
===================================================================
Runs alongside api_server.py on the Pi 5.

Flow
----
1. LISTEN  : record 5 s from USB/I2S mic via arecord
2. TRANSCRIBE : pass WAV to whisper.cpp → transcript text
3. THINK   : send transcript to agent.run() → answer text
4. PUSH    : POST /voice_query → api_server stores pending result
             Zero 2 W polls /pending_voice → shows transcript + answer
             Pico 2 LCD shows LISTENING → THINKING → WAITING
5. WAIT    : block until /confirm is called by Zero 2 W (K1 or K3)
             api_server notifies us via registered callback
6a. CONFIRM: espeak/piper speaks answer aloud through speaker
             POST /confirm {"confirmed": true} already sent by Zero 2 W
6b. REJECT : discard, go back to step 1

Usage
-----
  # In one terminal:
  python hardware/pi5/api_server.py --config hardware/pi5/config_pi5.yaml

  # In another terminal (or systemd service):
  python hardware/pi5/voice_loop.py

  # Override mic and whisper paths:
  MIC_DEVICE=hw:1,0 WHISPER_BIN=/home/pi/whisper.cpp/main \\
      python hardware/pi5/voice_loop.py

Dependencies
------------
  sudo apt-get install -y alsa-utils espeak-ng
  # whisper.cpp: https://github.com/ggerganov/whisper.cpp
  #   git clone ... && cd whisper.cpp && make
  #   bash models/download-ggml-model.sh tiny.en

Group 3 — ITAI2376-14562
Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess
import tempfile
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s — %(message)s",
)
log = logging.getLogger("shape.voice")

# ---------------------------------------------------------------------------
# Configuration — override via environment variables
# ---------------------------------------------------------------------------
API_BASE      = os.getenv("SHAPE_API_URL",   "http://localhost:8765")
API_KEY       = os.getenv("SHAPE_API_KEY",   "shape_local_key")
MIC_DEVICE    = os.getenv("MIC_DEVICE",      "hw:1,0")
WHISPER_BIN   = os.getenv("WHISPER_BIN",     "/home/pi/whisper.cpp/main")
WHISPER_MODEL = os.getenv("WHISPER_MODEL",   "/home/pi/whisper.cpp/models/ggml-tiny.en.bin")
TTS_CMD       = os.getenv("SHAPE_TTS_CMD",   "espeak-ng")  # or "piper --model ..."
RECORD_SECS   = int(os.getenv("RECORD_SECS", "5"))
CONFIRM_TIMEOUT = float(os.getenv("CONFIRM_TIMEOUT_S", "60"))  # wait up to 60 s

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def _post(path: str, data: dict, timeout: int = 30) -> dict:
    url  = API_BASE + path
    body = json.dumps(data).encode()
    req  = urllib.request.Request(url, data=body, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _post_wav(path: str, wav_bytes: bytes, timeout: int = 35) -> dict:
    url = API_BASE + path
    hdrs = {**_headers(), "Content-Type": "audio/wav"}
    req  = urllib.request.Request(url, data=wav_bytes, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Step 1 — Record from mic
# ---------------------------------------------------------------------------

def record_wav(seconds: int = RECORD_SECS, device: str = MIC_DEVICE) -> Path:
    """Record audio and return path to a temporary WAV file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out = Path(tmp.name)
    cmd = [
        "arecord",
        "-D", device,
        "-f", "S16_LE",
        "-r", "16000",
        "-c", "1",
        "-d", str(seconds),
        str(out),
    ]
    log.info("Recording %ds from %s …", seconds, device)
    subprocess.run(cmd, check=True, capture_output=True)
    log.info("Recording complete: %.1f KB", out.stat().st_size / 1024)
    return out


# ---------------------------------------------------------------------------
# Step 2 — Transcribe via whisper.cpp (local, offline)
# ---------------------------------------------------------------------------

def transcribe(wav_path: Path) -> str:
    """Run whisper.cpp on a WAV file and return the transcript text."""
    if not Path(WHISPER_BIN).exists():
        log.warning("whisper.cpp binary not found at %s — using /transcribe API fallback", WHISPER_BIN)
        # Fall back: POST to api_server /transcribe endpoint
        wav_bytes = wav_path.read_bytes()
        result = _post_wav("/transcribe", wav_bytes, timeout=35)
        return result.get("text", "")

    result = subprocess.run(
        [WHISPER_BIN, "-m", WHISPER_MODEL,
         "-f", str(wav_path), "--no-timestamps", "-otxt"],
        capture_output=True, text=True, timeout=30,
    )
    text = result.stdout.strip()
    if not text and result.stderr:
        # whisper sometimes writes to stderr
        text = result.stderr.strip().splitlines()[-1]
    log.info("Transcribed: %s", text[:80])
    return text


# ---------------------------------------------------------------------------
# Step 3 — Query agent (via local API)
# ---------------------------------------------------------------------------

def ask_agent(transcript: str) -> str:
    """POST transcript to /query and return the agent's answer."""
    log.info("Querying agent: %s", transcript[:60])
    result = _post("/query", {"input": transcript}, timeout=120)
    answer = result.get("output", "[No response]")
    log.info("Agent answer: %s", answer[:80])
    return answer


# ---------------------------------------------------------------------------
# Step 4 — Push to Zero 2 W confirmation queue
# ---------------------------------------------------------------------------

def push_for_confirmation(transcript: str, answer: str) -> str | None:
    """
    POST /voice_query so api_server holds the pending result.
    Zero 2 W polls /pending_voice and shows the confirmation screen.
    Returns the query_id string, or None on failure.
    """
    try:
        result = _post("/voice_query", {"transcript": transcript, "answer": answer})
        qid = result.get("query_id")
        log.info("Pending voice query registered: id=%s", qid)
        return qid
    except Exception as exc:
        log.error("Failed to register voice query: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Step 5 — Wait for confirmation from Zero 2 W
# ---------------------------------------------------------------------------

def wait_for_confirmation(query_id: str, timeout: float = CONFIRM_TIMEOUT) -> bool | None:
    """
    Poll /pending_voice until it clears (Zero 2 W called /confirm) or timeout.
    Returns True if confirmed, False if rejected, None on timeout.
    """
    deadline = time.time() + timeout
    log.info("Waiting for user confirmation (id=%s, timeout=%ds) …", query_id, int(timeout))
    while time.time() < deadline:
        try:
            result = _post("/pending_voice" if False else None, {}) \
                if False else json.loads(
                    urllib.request.urlopen(
                        urllib.request.Request(
                            API_BASE + "/pending_voice",
                            headers=_headers(),
                            method="GET",
                        ),
                        timeout=5,
                    ).read()
                )
            if not result.get("pending", True):
                # Cleared — the /confirm endpoint tells us the outcome via the
                # server log, but we don't know confirmed/rejected from polling.
                # We track it via a threading.Event set by the callback below.
                return _confirm_event.result
        except Exception:
            pass
        time.sleep(0.5)
    log.warning("Confirmation timeout for id=%s", query_id)
    return None


# Shared result object written by the _confirm_cb callback
class _ConfirmResult:
    def __init__(self):
        self.result: bool | None = None
        self._event = threading.Event()

    def set(self, confirmed: bool):
        self.result = confirmed
        self._event.set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)

    def reset(self):
        self.result = None
        self._event.clear()


_confirm_event = _ConfirmResult()


# ---------------------------------------------------------------------------
# Step 6 — Speak confirmed answer aloud
# ---------------------------------------------------------------------------

def speak(text: str) -> None:
    """Speak text through the speaker using espeak-ng (or piper)."""
    # Strip markdown-style formatting that sounds bad spoken
    clean = text.replace("**", "").replace("*", "").replace("`", "").replace("#", "")
    clean = clean[:500]   # cap length for showcase
    log.info("Speaking: %s …", clean[:60])
    try:
        subprocess.run([TTS_CMD, clean], check=True, capture_output=True)
    except FileNotFoundError:
        log.warning("TTS command '%s' not found. Install: sudo apt-get install espeak-ng", TTS_CMD)
    except subprocess.CalledProcessError as exc:
        log.warning("TTS failed: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _register_callback():
    """Register our confirmation callback with api_server's _voice_callbacks list."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    try:
        import hardware.pi5.api_server as _srv
        def _cb(confirmed: bool, answer: str):
            _confirm_event.set(confirmed)
        _srv._voice_callbacks.append(_cb)
        log.info("Registered voice confirmation callback with api_server.")
    except ImportError:
        log.warning("Could not register callback — api_server not importable from here. "
                    "Make sure voice_loop.py runs in the same process as api_server.py, "
                    "or use the standalone mode (poll /pending_voice manually).")


def run():
    _register_callback()

    # Connect to Pico 2 over USB — silently continues if not plugged in
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hardware.pi5.pico_usb import PicoUSB
    pico = PicoUSB()

    log.info("SHAPE voice loop started. Listening on mic device: %s", MIC_DEVICE)
    log.info("Whisper: %s  |  TTS: %s  |  Pico: %s",
             WHISPER_BIN, TTS_CMD, pico._port or "not connected")

    while True:
        wav_path = None
        try:
            _confirm_event.reset()

            # ── Step 1: Record ────────────────────────────────────────────
            pico.listening()          # Pico 2 LCD → pulsing LISTENING screen
            wav_path = record_wav()

            # ── Step 2: Transcribe ────────────────────────────────────────
            transcript = transcribe(wav_path)
            if not transcript.strip():
                log.info("Empty transcription — discarding, listening again.")
                pico.status("Nothing heard")
                continue

            # ── Step 3: Ask agent ─────────────────────────────────────────
            pico.thinking()           # Pico 2 LCD → spinning THINKING screen
            answer = ask_agent(transcript)

            # ── Step 4: Push to Zero 2 W for confirmation ─────────────────
            # Pico stays on THINKING while Zero 2 W user reads the answer
            query_id = push_for_confirmation(transcript, answer)
            if query_id is None:
                log.warning("Could not register voice query — speaking directly.")
                pico.confirmed(answer)
                speak(answer)
                continue

            # ── Step 5: Wait for Zero 2 W K1/K3 ──────────────────────────
            confirmed = _confirm_event.wait(CONFIRM_TIMEOUT)
            if confirmed is None or not _confirm_event.result:
                log.info("Voice query rejected or timed out — discarding answer.")
                pico.rejected()       # Pico 2 LCD → red REJECTED screen (4 s)
                continue

            # ── Step 6: Confirmed — speak answer ──────────────────────────
            pico.confirmed(answer)    # Pico 2 LCD → green CONFIRMED screen (4 s)
            speak(answer)
            pico.status("Ready", reward=1.0)

        except KeyboardInterrupt:
            log.info("Voice loop stopped.")
            pico.reset()
            pico.close()
            break
        except subprocess.CalledProcessError as exc:
            log.warning("Recording failed (mic not connected?): %s", exc)
            pico.status("Mic error")
            time.sleep(2)
        except Exception as exc:
            log.error("Voice loop error: %s", exc)
            pico.status("Error")
            time.sleep(1)
        finally:
            if wav_path and wav_path.exists():
                try:
                    wav_path.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    run()
