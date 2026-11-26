"""
shape.sensors — Sensor data ingestion and validation for SHAPE.

Handles parsing of Pico 2 UART CSV telemetry and validating sensor readings
before they are forwarded to the agent.  Used by the Zero 2 W serial bridge
and demonstrated in Notebook 03.

UART CSV format (from hardware/pico2/main.py):
    SHAPE,{ts_ms},{temp_c:.2f},{humidity_pct:.1f},{aqi:.0f},{alert:d}\r\n

Group 3 — ITAI2376-14562
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# Alert thresholds — same values used in hardware/pi5/api_server.py
AQI_ALERT_THRESHOLD  = 600   # ppm
TEMP_ALERT_THRESHOLD = 40.0  # °C

_CSV_PATTERN = re.compile(
    r"^SHAPE,(\d+),(-?[\d.]+),([\d.]+),([\d.]+),([01])$"
)


@dataclass
class SensorReading:
    """One telemetry sample from the Pico 2."""
    ts_ms:       int
    temperature: float
    humidity:    float
    aqi:         float
    alert:       bool

    @property
    def is_alert(self) -> bool:
        """True if any threshold is exceeded OR the hardware alert flag is set."""
        return (
            self.alert
            or self.aqi  > AQI_ALERT_THRESHOLD
            or self.temperature > TEMP_ALERT_THRESHOLD
        )

    @property
    def alert_reason(self) -> str:
        """Human-readable alert reason string for auto-query construction."""
        parts = []
        if self.aqi > AQI_ALERT_THRESHOLD or self.alert:
            parts.append(f"AQI={self.aqi:.0f}")
        if self.temperature > TEMP_ALERT_THRESHOLD:
            parts.append(f"temp={self.temperature:.1f}°C")
        return ", ".join(parts) if parts else "sensor alert"


def parse_csv_line(line: str) -> Optional[SensorReading]:
    """
    Parse one UART CSV line from the Pico 2.

    Returns a SensorReading on success, None if the line is malformed.
    Malformed lines are silently dropped — the bridge continues with the
    next sample rather than crashing.
    """
    m = _CSV_PATTERN.match(line.strip())
    if not m:
        return None
    try:
        return SensorReading(
            ts_ms=int(m.group(1)),
            temperature=float(m.group(2)),
            humidity=float(m.group(3)),
            aqi=float(m.group(4)),
            alert=bool(int(m.group(5))),
        )
    except (ValueError, IndexError):
        return None


def validate_reading(reading: SensorReading) -> list[str]:
    """
    Return a list of validation warnings for a SensorReading.

    An empty list means the reading is within normal operating ranges.
    Warnings do not block processing — they are appended to the agent query
    when an alert fires.
    """
    warnings: list[str] = []
    if not -40 <= reading.temperature <= 85:
        warnings.append(f"temperature {reading.temperature}°C out of DHT22 range (-40..85)")
    if not 0 <= reading.humidity <= 100:
        warnings.append(f"humidity {reading.humidity}% out of range (0..100)")
    if reading.aqi < 0:
        warnings.append(f"AQI {reading.aqi} is negative — sensor fault?")
    return warnings
