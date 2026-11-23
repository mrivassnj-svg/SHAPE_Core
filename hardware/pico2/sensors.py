"""
sensors.py — DHT22 temperature/humidity + MQ-135 air-quality sensor reader
Runs on Raspberry Pi Pico 2 (MicroPython).

Wiring:
  DHT22 DATA → GP22   (3.3 V power, 10 kΩ pull-up to 3.3 V)
  MQ-135 AO  → GP26   (ADC0 — analogue output)
  MQ-135 DO  → GP27   (digital threshold output, optional)
"""

import machine
import dht      # MicroPython built-in DHT driver
import time


# ── pin assignments ───────────────────────────────────────────────────────────

_DHT_PIN   = 22   # GP22 — DHT22 data
_MQ_AO_PIN = 26   # GP26 — ADC0 for MQ-135 analogue
_MQ_DO_PIN = 27   # GP27 — MQ-135 digital alert (active-low)


class SensorHub:
    """Reads DHT22 and MQ-135; exposes the last-good values."""

    # MQ-135 calibration: map raw 16-bit ADC value to a 0–1000 AQI-like index.
    # Adjust _MQ_SCALE for your specific sensor's load resistor / VCC.
    _MQ_SCALE = 1000 / 65535

    def __init__(self):
        self._dht  = dht.DHT22(machine.Pin(_DHT_PIN))
        self._adc  = machine.ADC(_MQ_AO_PIN)
        self._mq_do = machine.Pin(_MQ_DO_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

        # Last-good readings (populated after first successful measure())
        self.temperature  = None   # °C
        self.humidity     = None   # %
        self.aqi          = None   # 0-1000 index (0=clean, 1000=very polluted)
        self.air_alert    = False  # True when MQ-135 digital pin fires

        self._last_ok     = False
        self._err_count   = 0

    # ── public API ────────────────────────────────────────────────────────────

    def measure(self) -> bool:
        """
        Trigger a measurement cycle.
        Returns True if DHT22 reading succeeded (MQ-135 always succeeds).
        Updates self.temperature, self.humidity, self.aqi, self.air_alert.
        """
        # MQ-135 — read analogue (always succeeds)
        raw = self._adc.read_u16()
        self.aqi = round(raw * self._MQ_SCALE, 1)
        self.air_alert = not self._mq_do.value()   # active-low

        # DHT22 — can fail; keep last-good values on failure
        try:
            self._dht.measure()
            self.temperature = self._dht.temperature()
            self.humidity    = self._dht.humidity()
            self._last_ok    = True
            self._err_count  = 0
            return True
        except OSError:
            self._err_count += 1
            self._last_ok    = False
            return False

    def as_dict(self) -> dict:
        """Return current readings as a plain dict (JSON-serialisable)."""
        return {
            "temperature": self.temperature,
            "humidity":    self.humidity,
            "aqi":         self.aqi,
            "air_alert":   self.air_alert,
            "dht_ok":      self._last_ok,
        }

    def csv_row(self, ts_ms: int) -> str:
        """Return a CSV row: timestamp_ms,temp,humidity,aqi,alert"""
        t  = f"{self.temperature:.1f}" if self.temperature is not None else "ERR"
        h  = f"{self.humidity:.1f}"    if self.humidity    is not None else "ERR"
        aq = f"{self.aqi:.1f}"         if self.aqi         is not None else "ERR"
        al = "1" if self.air_alert else "0"
        return f"{ts_ms},{t},{h},{aq},{al}"

    @property
    def is_healthy(self) -> bool:
        """True if the last DHT22 read succeeded."""
        return self._last_ok

    @property
    def consecutive_errors(self) -> int:
        return self._err_count
