#!/usr/bin/env python3
"""Мини-контроллеры Tasmota/Shelly/свой HTTP для проверки DirectClient на JVM."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

STATE = {
    "tasmota": {"Power": "OFF", "Power2": "OFF"},
    "shelly1": {"on": False},
    "shelly2": {"on": False},
    "custom": {"state": "CLOSED"},
}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text):
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _off_later(self, key, delay):
        def off():
            with LOCK:
                STATE[key]["on"] = False
        threading.Timer(delay, off).start()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        if path.startswith("/mockha/api/services/"):
            if self.headers.get("Authorization") != "Bearer test-token":
                self._json({"error": "unauthorized"}, 401)
                return
            try:
                body = json.loads(raw)
            except Exception:
                self._json({"error": "bad json"}, 400)
                return
            if body.get("entity_id") != "cover.gate":
                self._json({"error": "bad entity"}, 400)
                return
            self._json({})
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)

        if path == "/tasmota/cm":
            cmnd = (q.get("cmnd", [""])[0] or "").strip()
            parts = cmnd.split()
            cmd = parts[0] if parts else "Power"
            action = parts[1].upper() if len(parts) > 1 else ""
            with LOCK:
                cur = STATE["tasmota"].get(cmd, "OFF")
                if action == "TOGGLE":
                    cur = "OFF" if cur == "ON" else "ON"
                elif action == "ON":
                    cur = "ON"
                elif action == "OFF":
                    cur = "OFF"
                STATE["tasmota"][cmd] = cur
            self._json({cmd: cur})
            return

        if path == "/shelly1/status":
            self._json({"relays": [{"ison": STATE["shelly1"]["on"]}]})
            return

        if path.startswith("/shelly1/relay/"):
            turn = q.get("turn", [""])[0]
            with LOCK:
                if turn == "toggle":
                    STATE["shelly1"]["on"] = not STATE["shelly1"]["on"]
                elif turn == "on":
                    STATE["shelly1"]["on"] = True
                elif turn == "off":
                    STATE["shelly1"]["on"] = False
                on = STATE["shelly1"]["on"]
            if "timer" in q:
                self._off_later("shelly1", float(q["timer"][0]))
            self._json({"ison": on})
            return

        if path == "/shelly2/rpc/Shelly.GetStatus":
            self._json({"switch:0": {"output": STATE["shelly2"]["on"]}})
            return

        if path == "/shelly2/rpc/Switch.Toggle":
            with LOCK:
                STATE["shelly2"]["on"] = not STATE["shelly2"]["on"]
                on = STATE["shelly2"]["on"]
            self._json({"was_on": not on})
            return

        if path == "/shelly2/rpc/Switch.Set":
            on = q.get("on", ["true"])[0].lower() == "true"
            with LOCK:
                STATE["shelly2"]["on"] = on
            if "toggle_after" in q:
                self._off_later("shelly2", float(q["toggle_after"][0]))
            self._json({})
            return

        if path == "/custom/open":
            with LOCK:
                STATE["custom"]["state"] = "OPEN"
            self._json({"ok": True})
            return

        if path == "/custom/close":
            with LOCK:
                STATE["custom"]["state"] = "CLOSED"
            self._json({"ok": True})
            return

        if path == "/custom/status":
            self._json({"state": STATE["custom"]["state"]})
            return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    print("mock on :18080", flush=True)
    HTTPServer(("127.0.0.1", 18080), Handler).serve_forever()
