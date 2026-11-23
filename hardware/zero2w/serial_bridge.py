"""
serial_bridge.py — UART serial bridge on the Zero 2 W (Tier 2)

Responsibilities:
  1. Read CSV telemetry lines from the Pico 2 over UART (/dev/ttyAMA1 by default)
  2. Parse each line and POST sensor data to the Pi 5 HTTP API
  3. Receive JSON responses from the Pi 5 API and forward them back to the Pico 2
  4. Run as a background daemon thread inside main_zero2w.py

Wiring (Zero 2 W GPIO header):
  UART TX → GPIO14 (physical pin 8)  → Pico 2 GP1 (RX)
  UART RX → GPIO15 (physical pin 10) → Pico 2 GP0 (TX)
  GND     → any GND pin              → Pico 2 GND

/boot/config.txt additions required:
  enable_uart=1
  dtoverlay=disable-bt        # free up the PL011 UART from Bluetooth

Then:
  sudo systemctl disable hciuart
  sudo reboot
"""

import serial
import threading
import requests
import json
import time
import logging


# ── configuration ─────────────────────────────────────────────────────────────

UART_PORT    = "/dev/ttyAMA1"   # PL011 UART (reliable); /dev/serial0 also works
UART_BAUD    = 115_200
UART_TIMEOUT = 1.0              # seconds read timeout

PI5_API_BASE = "http://192.168.1.100:5000"   # Pi 5 API server address
API_TIMEOUT  = 10.0             # seconds for HTTP call

# How often (seconds) to push a background heartbeat status to the Pico 2
HEARTBEAT_S  = 30.0


log = logging.getLogger("serial_bridge")


# ── data model ────────────────────────────────────────────────────────────────

class SensorReading:
    """Parsed telemetry from a Pico 2 CSV line."""
    __slots__ = ("ts_ms", "temperature", "humidity", "aqi", "alert", "raw")

    def __init__(self, ts_ms, temperature, humidity, aqi, alert, raw):
        self.ts_ms       = ts_ms
        self.temperature = temperature
        self.humidity    = humidity
        self.aqi         = aqi
        self.alert       = alert
        self.raw         = raw

    def to_dict(self):
        return {
            "source":      "pico2",
            "ts_ms":       self.ts_ms,
            "temperature": self.temperature,
            "humidity":    self.humidity,
            "aqi":         self.aqi,
            "air_alert":   self.alert,
        }


def _parse_csv(line: str):
    """
    Parse a Pico 2 CSV line: SHAPE,{ts_ms},{temp},{humidity},{aqi},{alert}
    Returns SensorReading or None on parse failure.
    """
    try:
        parts = line.strip().split(",")
        if len(parts) != 6 or parts[0] != "SHAPE":
            return None
        return SensorReading(
            ts_ms       = int(parts[1]),
            temperature = float(parts[2]) if parts[2] != "ERR" else None,
            humidity    = float(parts[3]) if parts[3] != "ERR" else None,
            aqi         = float(parts[4]) if parts[4] != "ERR" else None,
            alert       = parts[5] == "1",
            raw         = line,
        )
    except (ValueError, IndexError):
        return None


# ── bridge ────────────────────────────────────────────────────────────────────

class SerialBridge:
    """
    Bidirectional bridge between Pico 2 UART and Pi 5 HTTP API.
    Designed to be started as a daemon thread from main_zero2w.py.
    """

    def __init__(self, uart_port=UART_PORT, uart_baud=UART_BAUD,
                 pi5_base=PI5_API_BASE):
        self._port     = uart_port
        self._baud     = uart_baud
        self._pi5_base = pi5_base
        self._ser      = None
        self._running  = False
        self._send_q   = []        # list[str] — JSON strings to push to Pico 2
        self._lock     = threading.Lock()

        # Latest parsed reading — readable from main_zero2w.py
        self.latest_reading = None
        self.last_pi5_reply = None
        self.error_count    = 0

    # ── public API ────────────────────────────────────────────────────────────

    def start(self):
        """Open UART and launch reader + writer threads."""
        try:
            self._ser = serial.Serial(
                self._port, self._baud,
                timeout=self._uart_timeout_val(),
            )
        except serial.SerialException as e:
            log.error("Cannot open UART %s: %s", self._port, e)
            return False
        self._running = True
        threading.Thread(target=self._reader_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        log.info("SerialBridge started on %s @ %d baud → %s",
                 self._port, self._baud, self._pi5_base)
        return True

    def stop(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def push_to_pico(self, cmd: str, text: str = "", reward: float = None):
        """
        Queue a JSON command for the Pico 2.
        cmd: "STATUS" | "ALERT" | "RESET"
        """
        payload = {"cmd": cmd}
        if text:
            payload["text"] = text
        if reward is not None:
            payload["reward"] = round(float(reward), 3)
        with self._lock:
            self._send_q.append(json.dumps(payload) + "\r\n")

    # ── internal ──────────────────────────────────────────────────────────────

    def _uart_timeout_val(self):
        return UART_TIMEOUT

    def _reader_loop(self):
        """Read CSV lines from Pico 2 and forward sensor data to Pi 5."""
        while self._running:
            try:
                raw = self._ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                log.debug("UART ← %s", line)
                reading = _parse_csv(line)
                if reading is None:
                    log.warning("Unrecognised UART line: %s", line)
                    continue

                self.latest_reading = reading

                # Forward to Pi 5
                reply = self._post_sensor(reading)
                if reply:
                    self.last_pi5_reply = reply
                    # Send reply back to Pico 2
                    cmd  = reply.get("cmd", "STATUS")
                    text = reply.get("text", "")
                    rw   = reply.get("reward")
                    self.push_to_pico(cmd, text, rw)
                    self._flush_send_queue()

            except serial.SerialException as e:
                log.error("UART read error: %s", e)
                self.error_count += 1
                time.sleep(1)
            except Exception as e:
                log.error("Unexpected error in reader: %s", e)
                self.error_count += 1

    def _post_sensor(self, reading: SensorReading) -> dict:
        """
        POST sensor telemetry to the Pi 5 /sensor endpoint.
        Returns the parsed JSON response dict, or None on failure.
        """
        url = f"{self._pi5_base}/sensor"
        try:
            resp = requests.post(url, json=reading.to_dict(), timeout=API_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            log.warning("Pi 5 POST failed: %s", e)
            return None

    def _heartbeat_loop(self):
        """
        Periodically ask the Pi 5 for agent status and push it to the Pico 2.
        Also flushes any queued outbound messages.
        """
        while self._running:
            time.sleep(HEARTBEAT_S)
            status = self._get_pi5_status()
            if status:
                self.push_to_pico("STATUS",
                                  status.get("status", "OK"),
                                  status.get("avg_reward"))
            self._flush_send_queue()

    def _get_pi5_status(self) -> dict:
        url = f"{self._pi5_base}/status"
        try:
            resp = requests.get(url, timeout=API_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            log.warning("Pi 5 GET /status failed: %s", e)
            return None

    def _flush_send_queue(self):
        """Write all queued JSON lines to the Pico 2 UART."""
        with self._lock:
            items = list(self._send_q)
            self._send_q.clear()
        for item in items:
            try:
                self._ser.write(item.encode("utf-8"))
                log.debug("UART → %s", item.strip())
            except serial.SerialException as e:
                log.error("UART write error: %s", e)


# ── standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    bridge = SerialBridge()
    if not bridge.start():
        raise SystemExit("Could not open UART — check wiring and /boot/config.txt")

    log.info("Bridge running. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(5)
            if bridge.latest_reading:
                r = bridge.latest_reading
                log.info("Latest: %.1f°C  %.1f%%RH  AQI=%.0f  alert=%s",
                         r.temperature or 0, r.humidity or 0,
                         r.aqi or 0, r.alert)
    except KeyboardInterrupt:
        bridge.stop()
        log.info("Bridge stopped.")
