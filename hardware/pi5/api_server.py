"""
Pi 5 API server — exposes SHAPE agent over local Wi-Fi HTTP
so the Zero 2 W can query it without SSH.

Run:  python hardware/pi5/api_server.py --config hardware/pi5/config_pi5.yaml

Group 3 — ITAI2376-14562
Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shape.agent import build_agent

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("shape.api")

# Global agent instance (loaded once at startup)
_agent   = None
_api_key = "shape_local_key"
# Ring buffer of last 20 sensor readings from Pico 2
_sensor_history: list = []
_SENSOR_MAX = 20


class SHAPEHandler(BaseHTTPRequestHandler):
    """
    Minimal HTTP API — five endpoints:

      POST /query        body: {"input": "..."}
                         returns: {"output": "..."}

      POST /feedback     body: {"input":"...","output":"...","score":4}
                         returns: {"ok": true}

      GET  /status       returns: {"model":"...","rl":{"avg":4.2,...}}

      POST /reset        clears conversation memory

      POST /sensor       body: {"source":"pico2","temperature":24.5,...}
                         returns: {"cmd":"STATUS","text":"...","reward":0.9}
                         (also injects alert queries automatically)
    """

    def _auth(self) -> bool:
        key = self.headers.get("X-API-Key", "")
        return key == _api_key

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def do_GET(self):
        if not self._auth():
            return self._send_json(401, {"error": "Unauthorized"})
        path = urlparse(self.path).path
        if path == "/status":
            rl = _agent.feedback.summary()
            self._send_json(200, {
                "model":      _agent.config.get("model"),
                "rl":         rl,
                "avg_reward": rl.get("avg_score"),
                "status":     "ready",
            })
        elif path == "/sensors":
            self._send_json(200, {"readings": _sensor_history})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._auth():
            return self._send_json(401, {"error": "Unauthorized"})
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/query":
            user_input = body.get("input", "").strip()
            if not user_input:
                return self._send_json(400, {"error": "Missing 'input'"})
            log.info("Query: %s", user_input[:60])
            output = _agent.run(user_input)
            self._send_json(200, {"output": output})

        elif path == "/feedback":
            try:
                _agent.collect_feedback(
                    body["input"], body["output"], int(body["score"])
                )
                self._send_json(200, {"ok": True})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})

        elif path == "/reset":
            _agent.reset_session()
            self._send_json(200, {"ok": True})

        elif path == "/sensor":
            # Store the reading
            global _sensor_history
            _sensor_history.append(body)
            if len(_sensor_history) > _SENSOR_MAX:
                _sensor_history = _sensor_history[-_SENSOR_MAX:]

            # Auto-generate an alert query if conditions are critical
            aqi   = body.get("aqi")
            temp  = body.get("temperature")
            alert = body.get("air_alert", False)

            if alert or (aqi and aqi > 600) or (temp and temp > 40):
                concern = []
                if alert or (aqi and aqi > 600):
                    concern.append(f"AQI={aqi:.0f}" if aqi else "air alert")
                if temp and temp > 40:
                    concern.append(f"temp={temp:.1f}°C")
                query = ("SHAPE ALERT from Pico 2 sensor: "
                         + ", ".join(concern)
                         + ". What action should be taken?")
                log.info("Auto-query triggered: %s", query[:60])
                try:
                    output = _agent.run(query)
                    rl     = _agent.feedback.summary()
                    self._send_json(200, {
                        "cmd":    "ALERT",
                        "text":   output[:120],
                        "reward": rl.get("avg_score"),
                    })
                except Exception as exc:
                    self._send_json(200, {"cmd": "STATUS", "text": "Agent busy"})
            else:
                rl = _agent.feedback.summary()
                self._send_json(200, {
                    "cmd":    "STATUS",
                    "text":   "Sensors nominal",
                    "reward": rl.get("avg_score"),
                })

        else:
            self._send_json(404, {"error": "Not found"})

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


def main():
    global _agent, _api_key
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="hardware/pi5/config_pi5.yaml")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    _api_key = config.get("api_key", _api_key)
    host = config.get("api_host", "0.0.0.0")
    port = config.get("api_port", 8765)

    log.info("Loading SHAPE agent (model=%s)…", config.get("model", "codellama"))
    _agent = build_agent(config)
    log.info("Agent ready.")

    server = HTTPServer((host, port), SHAPEHandler)
    log.info("SHAPE API listening on http://%s:%d", host, port)
    log.info("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
