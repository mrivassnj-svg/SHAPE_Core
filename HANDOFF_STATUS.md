# SHAPE — Final Submission Status
**Group 3 | ITAI2376-14562**

---

## Deliverables

| File | Status | Location |
|---|---|---|
| Demo video | ✅ | `demo/output/FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4` |
| Project report | ✅ | `docs/FN_Report_MichaelRivas_Group3_ITAI2376_14562.pdf` |
| Notebook 1 | ✅ | `notebooks/01_SHAPE_Introduction.ipynb` |
| Notebook 2 | ✅ | `notebooks/02_SHAPE_ReAct_Engine.ipynb` |
| Notebook 3 | ✅ | `notebooks/03_SHAPE_Tools_Environment.ipynb` |
| Notebook 4 | ✅ | `notebooks/04_SHAPE_Evaluation_Demo.ipynb` |
| Interactive visualizer | ✅ | `notebooks/shape_react_visualizer.html` |
| Unit tests (32 passing) | ✅ | `tests/` |

---

## Voice Showcase Rig (hardware upgrade)

The original three-tier sensor architecture (Pico 2 → Zero 2 W → Pi 5) has
been extended with a voice interaction pipeline. Physical DHT22/MQ-135 sensors
are **not required** — the Pico 2 now acts as the visual confirmation panel.

---

### Physical wiring diagram

```
╔══════════════════════════════════════════════════════════════════╗
║                     SHAPE SHOWCASE RIG                          ║
║                                                                  ║
║  ┌─────────────────────┐         ┌─────────────────────────┐   ║
║  │  Raspberry Pi       │         │  Raspberry Pi Zero 2 W  │   ║
║  │  Pico 2             │         │  + Waveshare 1.3" HAT   │   ║
║  │  + Waveshare        │         │                         │   ║
║  │    Pico-LCD-1.3 HAT │         │  LCD 240×240  (SPI0)    │   ║
║  │                     │         │  K1 K2 K3  (GPIO 21/20/16)  ║
║  │  LCD 240×240 (SPI0) │         │  Joystick  (GPIO 6/19/26)   ║
║  │  ABXY keys          │         │                         │   ║
║  │  Joystick           │         │  UART TX  GPIO 14 ──────┼──┐║
║  │                     │         │  UART RX  GPIO 15 ──────┼─┐│║
║  │  GP0 (TX) ──────────┼─────────┼── GPIO 15 (RX)          │ ││║
║  │  GP1 (RX) ──────────┼─────────┼── GPIO 14 (TX)          │ ││║
║  │  GND ───────────────┼─────────┼── GND                   │ ││║
║  └─────────────────────┘         └─────────────────────────┘ ││║
║                                              Wi-Fi Direct  ↕  ││║
║                                         (Pi 5 is hotspot)  ↕  ││║
║                                                             ↕  ││║
║                                  ┌─────────────────────────┐  ││║
║                                  │  Raspberry Pi 5         │  ││║
║                                  │                         │  ││║
║                                  │  Ollama + CodeLlama     │  ││║
║                                  │  api_server.py (:8765)  │  ││║
║                                  │  voice_loop.py          │  ││║
║                                  │                         │  ││║
║                                  │  USB mic ───────────────┤  ││║
║                                  │  3.5mm speaker ─────────┤  ││║
║                                  │  USB-C power ───────────┤  ││║
║                                  └─────────────────────────┘  ││║
╚════════════════════════════════════════════════════════════════╝│║
                                                                  └┘
  NOTE: The Zero 2 W HAT occupies all GPIO pins needed for a
  hardware wire to the Pi 5.  Wi-Fi Direct is used for the
  Zero 2 W <-> Pi 5 link — no router, no internet, fully offline.
  The Pi 5 creates its own private hotspot (10.42.0.1/24).
```

**Why Wi-Fi Direct and not a cable for Zero 2 W ↔ Pi 5?**

The Zero 2 W HAT uses:
- GPIO 14/15 → already wired to Pico 2 UART
- GPIO 8/10/11/24/25/27 → SPI LCD
- GPIO 5/6/13/16/19/20/21/26 → buttons and joystick

There are no free UART pins left for a second hardware serial link.
Wi-Fi Direct keeps every existing HTTP call working unchanged — it is
just a private `10.42.0.0/24` network between the two devices with
the Pi 5 acting as the access point.

---

### Physical connections summary

| Link | Type | Wires / medium |
|---|---|---|
| Pico 2 → Zero 2 W | **UART (hardware)** | GP0(TX)→GPIO15, GP1(RX)→GPIO14, GND→GND |
| Zero 2 W → Pi 5 | **Wi-Fi Direct** | No physical wire — Pi 5 hotspot `SHAPE` |
| Mic → Pi 5 | USB | USB-A mic into Pi 5 USB port |
| Speaker → Pi 5 | 3.5 mm audio | Pi 5 headphone jack or USB DAC |
| Power | USB-C | Battery bank into Pi 5 USB-C; Pi 5 powers itself |

---

### One-time setup — Pi 5 hotspot

```bash
# Run once on the Pi 5 (creates a persistent hotspot that survives reboots):
sudo hardware/pi5/setup_hotspot.sh

# Pi 5 IP on the hotspot is always: 10.42.0.1
```

Then on the Zero 2 W (add to `~/.bashrc`):
```bash
export SHAPE_PI5_URL=http://10.42.0.1:8765
export SHAPE_API_KEY=shape_local_key
```

Connect the Zero 2 W to the `SHAPE` Wi-Fi network (password: `shapedemo`)
using the Raspberry Pi Imager advanced settings or `raspi-config`.

---

### Voice interaction data flow

```
Pi 5 mic records 5 s audio
  |
  v  whisper.cpp (offline STT — no internet)
  |
  v  agent.run() — CodeLlama 7B via Ollama
  |
  v  POST /voice_query  -->  api_server holds pending result
                                    |
                    Zero 2 W polls /pending_voice (every 1.5 s)
                                    |
                    PUSH_QUERY screen appears on Zero 2 W HAT:
                      top: "Heard: <transcript>"
                      bottom: SHAPE answer (paged with K2)
                      K1 = CONFIRM     K3 = REJECT
                                    |
                         K1 pressed               K3 pressed
                            |                        |
                   POST /confirm true       POST /confirm false
                   Pi 5 speaks answer       Pi 5 discards, re-listens
                            |
                   Zero 2 W sends UART:     Zero 2 W sends UART:
                   {"cmd":"CONFIRMED"}      {"cmd":"REJECTED"}
                            |                        |
                   Pico 2 LCD:              Pico 2 LCD:
                   green "OK / Speaking!"   red "RETRY"  (4 s)
```

---

### New / changed files

| File | What changed |
|---|---|
| `hardware/pi5/setup_hotspot.sh` | **New** — one-time Pi 5 hotspot creation script |
| `hardware/pi5/voice_loop.py` | **New** — record → transcribe → query → push → speak |
| `hardware/pi5/api_server.py` | Added `/voice_query`, `/confirm`, `/pending_voice` |
| `hardware/zero2w/hat_driver.py` | Added `screen_push_query()` |
| `hardware/zero2w/main_zero2w.py` | Added `PUSH_QUERY` state, voice poll thread, `_push_pico_cmd()` |
| `hardware/pico2/main.py` | Added `LISTENING / THINKING / CONFIRMED / REJECTED` display modes |

---

### How to run (complete startup sequence)

```bash
# ── Pi 5 (run in order) ────────────────────────────────────────────
# 1. Hotspot (already running after one-time setup — skippable)
sudo nmcli connection up SHAPE-Hotspot

# 2. SHAPE API server
python hardware/pi5/api_server.py --config hardware/pi5/config_pi5.yaml &

# 3. Voice loop
MIC_DEVICE=hw:1,0 python hardware/pi5/voice_loop.py &

# ── Zero 2 W ───────────────────────────────────────────────────────
# (after connecting to 'SHAPE' Wi-Fi)
python hardware/zero2w/main_zero2w.py

# ── Pico 2 ─────────────────────────────────────────────────────────
# Runs main.py automatically on power-up (boot.py)
```

---

### Dependencies for voice

```bash
# Pi 5:
sudo apt-get install -y alsa-utils espeak-ng

# whisper.cpp (one-time build, ~15 min on Pi 5):
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp && make
bash models/download-ggml-model.sh tiny.en

# Set env (add to ~/.bashrc on Pi 5):
export WHISPER_BIN=/home/pi/whisper.cpp/main
export WHISPER_MODEL=/home/pi/whisper.cpp/models/ggml-tiny.en.bin
```

---

## Notebook Chapter Map

| Notebook | Rubric coverage |
|---|---|
| 01 — Introduction & Architecture | Input processing, project option, 3-tier hardware, 10-step data flow |
| 02 — Agent & ReAct Engine | Memory, ReAct loop, output generation, 8-step cap |
| 03 — Tools & Environment | Two external tools, error handling, safety, sensor validation |
| 04 — Evaluation & Demo | RL before/after, reward trend, metrics, single-click full demo |

---

## Package Structure (shape/ v2.0.0)

```
shape/
├── agent.py        SHAPEAgent + build_agent()
├── parser.py       parse_llm_output()
├── memory.py       make_history(), trimmed_messages()
├── prompts.py      REACT_SYSTEM template
├── rewards.py      FeedbackMemory (RL loop)
├── safety.py       InputGuard
├── sensors.py      SensorReading, parse_csv_line()
└── tools/
    ├── code_executor.py
    ├── linter.py
    ├── file_manager.py
    └── doc_search.py
```

---

## Member Contributions

| Member | Primary modules | Notebooks verified |
|---|---|---|
| Michael Rivas | `shape/agent.py`, `main.py`, `hardware/pi5/api_server.py` | NB04 |
| Cherluk Sumdin | `shape/rewards.py` (RL feedback loop) | NB01 |
| Olubukola Kukoyi | `shape/tools/` (all 4 tools) | NB03 |
| Taki Eddine Boubekri | `shape/safety.py`, `hardware/pico2/` (firmware) | NB02 |
