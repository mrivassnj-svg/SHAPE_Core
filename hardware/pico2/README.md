# SHAPE Pico 2 — Firmware README

## Hardware
| Component | Detail |
|---|---|
| MCU | Raspberry Pi Pico 2 (RP2350, 264 KB SRAM, 4 MB flash) |
| Display HAT | Waveshare Pico-LCD-1.3 (240×240 ST7789, SPI) |
| Sensor 1 | DHT22 — temperature (−40–80 °C) + humidity (0–100 % RH) |
| Sensor 2 | MQ-135 — air-quality (CO₂, NH₃, alcohol; analogue + digital) |

## GPIO Pin Map

### LCD HAT (SPI1)
| Signal | GPIO |
|---|---|
| SPI CLK  | GP10 |
| SPI MOSI | GP11 |
| CS       | GP9  |
| DC       | GP8  |
| RST      | GP12 |
| Backlight| GP13 |

### Keys (active-LOW, internal pull-ups)
| Button | GPIO |
|---|---|
| Joystick UP    | GP2  |
| Joystick DOWN  | GP18 |
| Joystick LEFT  | GP16 |
| Joystick RIGHT | GP20 |
| Joystick PRESS | GP3  |
| A              | GP15 |
| B              | GP17 |
| X              | GP19 |
| Y              | GP21 |

### Sensors
| Sensor | Signal | GPIO |
|---|---|---|
| DHT22   | DATA      | GP22 |
| MQ-135  | Analogue  | GP26 (ADC0) |
| MQ-135  | Digital   | GP27 |

### UART to Zero 2 W
| Signal | GPIO |
|---|---|
| TX | GP0 |
| RX | GP1 |

Connect Pico GP0 (TX) → Zero 2 W GPIO15 (RX) and Pico GP1 (RX) → Zero 2 W GPIO14 (TX).  
Both share a common GND. **Do NOT connect 5 V lines** — the Pico is 3.3 V logic.

## Files
| File | Purpose |
|---|---|
| `boot.py`    | MicroPython boot config (GC tuning) |
| `main.py`    | Main firmware loop (UI state machine) |
| `st7789.py`  | ST7789 SPI LCD driver + 5×7 bitmap font |
| `sensors.py` | DHT22 + MQ-135 sensor driver |
| `keys.py`    | ABXY + joystick debounce handler |

## Flashing

```bash
# Install MicroPython on Pico 2 (hold BOOTSEL → drag UF2)
# Then copy all .py files to the Pico flash via mpremote:
pip install mpremote
mpremote connect /dev/ttyACM0 fs cp boot.py    :boot.py
mpremote connect /dev/ttyACM0 fs cp st7789.py  :st7789.py
mpremote connect /dev/ttyACM0 fs cp sensors.py :sensors.py
mpremote connect /dev/ttyACM0 fs cp keys.py    :keys.py
mpremote connect /dev/ttyACM0 fs cp main.py    :main.py
# Reset the Pico — firmware starts automatically
mpremote connect /dev/ttyACM0 reset
```

## UART Telemetry Protocol

**Pico → Zero 2 W (every 2 s):**
```
SHAPE,{uptime_ms},{temp_C},{humidity_%},{aqi_0-1000},{alert_0_or_1}
```
Example: `SHAPE,12340,24.5,55.2,145.3,0`

**Zero 2 W → Pico (JSON, newline-terminated):**
```json
{"cmd": "STATUS", "text": "Agent ready", "reward": 0.92}
{"cmd": "ALERT",  "text": "High AQI: 650"}
{"cmd": "RESET"}
```

## Key Bindings

| Key | Action |
|---|---|
| **A** | Cycle display mode: SENSOR → STATUS → RESPONSE → SENSOR |
| **B** | Force immediate sensor read + UART transmit |
| **X** | Clear active alert banner |
| **Y** | Jump to RESPONSE screen |
| **UP / DOWN** | Scroll RESPONSE screen (when in RESPONSE mode) |
