"""T-Duck protocol 1.0 reference simulator; never connects to motors."""
import argparse
import hashlib
import hmac
import json
import os
import ssl
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COMMANDS = ("stand", "rest", "forward", "left", "right", "stop", "recover")
MOVEMENT = ("forward", "left", "right")


class Robot:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.activity = "Resting"
        self.mode = "rest"
        self.status = "ready"
        self.deadline = 0
        self.acks = OrderedDict()
        self.warning = []

    def watchdog(self):
        with self.lock:
            if self.mode in MOVEMENT and self.clock() >= self.deadline:
                self.activity, self.mode = "Stopped safely", "stop"
                self.warning = ["Movement lease expired; local watchdog stopped motion"]

    def command(self, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            command, identity, ttl = (payload.get(k) for k in ("command", "id", "ttl_ms"))
            if not isinstance(identity, str) or not 1 <= len(identity) <= 128:
                raise ValueError("id must contain 1..128 characters")
            if command not in COMMANDS:
                raise ValueError("unsupported command")
            if type(ttl) is not int or not 100 <= ttl <= 1000:
                raise ValueError("ttl_ms must be an integer in 100..1000")
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if identity in self.acks:
                old_fingerprint, ack = self.acks[identity]
                if fingerprint != old_fingerprint:
                    raise ValueError("id already used with different payload")
                return ack  # Retries never extend a movement lease.
            self.mode = command
            self.activity = {"stand": "Standing", "rest": "Resting", "forward": "Walking forward",
                             "left": "Turning left", "right": "Turning right", "stop": "Stopped safely",
                             "recover": "Recovered to standing"}[command]
            if command == "recover":
                self.mode = "stand"
            self.status, self.warning = "ready", []
            self.deadline = self.clock() + ttl / 1000
            ack = {"id": identity, "accepted": True, "command": command, "status": "applied"}
            self.acks[identity] = fingerprint, ack
            if len(self.acks) > 1024:
                self.acks.popitem(last=False)
            return ack

    def telemetry(self):
        with self.lock:
            self.watchdog()
            return {"protocol_version": "1.0", "device_id": "t-duck-simulator-001", "simulated": True,
                    "battery_percent": 87, "battery_voltage": 7.8, "activity": self.activity,
                    "movement_mode": self.mode, "status": self.status, "warnings": self.warning,
                    "software_version": "0.1.0", "roll_deg": 1.2, "pitch_deg": -0.8, "yaw_deg": 12.0,
                    "left_contact": True, "right_contact": self.mode not in MOVEMENT,
                    "distance_cm": 120, "touch": False, "camera_available": False,
                    "temperature_c": 22.4, "motor_temperature_c": 31.0}


def make_server(host, port, token, robot=None):
    if len(token) < 24:
        raise ValueError("Use a random token of at least 24 characters")
    robot = robot or Robot()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Avoid accidental credential/body logging.

        def reply(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.reply(401, {"error": "unauthorized"})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path == "/v1/capabilities":
                self.reply(200, {"protocol_version": "1.0", "device_id": "t-duck-simulator-001",
                                 "name": "T-Duck simulator", "simulated": True,
                                 "commands": list(COMMANDS), "max_movement_lease_ms": 1000,
                                 "ota": False, "ble": False})
            elif self.path == "/v1/telemetry":
                self.reply(200, robot.telemetry())
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/v1/commands":
                self.reply(404, {"error": "not_found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    raise ValueError("body must contain 1..4096 bytes")
                self.connection.settimeout(2)
                payload = json.loads(self.rfile.read(size))
                self.reply(200, robot.command(payload))
            except (ValueError, UnicodeError) as exc:
                self.reply(400, {"error": "invalid_request", "reason": str(exc)})

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.timeout = 0.1
    server.robot = robot
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    parser.add_argument("--insecure-loopback", action="store_true", help="Explicit test-only HTTP")
    args = parser.parse_args()
    token = os.environ.get("T_DUCK_TOKEN", "")
    server = make_server(args.host, args.port, token)
    if args.insecure_loopback:
        if args.host not in ("127.0.0.1", "::1", "localhost"):
            parser.error("Test HTTP must bind loopback; use TLS for LAN")
    else:
        if not args.cert or not args.key:
            parser.error("TLS --cert and --key required (or explicit --insecure-loopback for tests)")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print("T-Duck simulator listening; all readings are simulated", flush=True)
    try:
        while True:
            server.handle_request()
            server.robot.watchdog()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
