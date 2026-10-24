"""Authenticated local HTTPS adapter to the pinned PR #2 MuJoCo controller.

Imports external source checkouts; never bundles geometry, weights or hardware code.
Only the simulation thread touches MuJoCo; movement intent has independent wall-clock expiry.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict
import copy
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import threading
import time
import uuid

LOCK = json.loads(Path(__file__).with_name("integration-lock.json").read_text())
COMMANDS = ("stand", "rest", "forward", "left", "right", "stop")
TWISTS = {"stand": (0., 0., 0.), "rest": (0., 0., 0.), "stop": (0., 0., 0.),
          "forward": (0.2, 0., 0.), "left": (0.1, 0., 0.5), "right": (0.1, 0., -0.5)}
MOVING = {"forward", "left", "right"}
DEVICE_ID = "t-duck-mujoco-001"


def load_foundation(path):
    revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if revision != LOCK["foundation_revision"]:
        raise ValueError("Foundation revision does not match integration lock")
    subprocess.run(["git", "-C", str(path), "diff", "--quiet", "HEAD", "--", "t_duck_eval.py"], check=True)
    spec = importlib.util.spec_from_file_location("tc02_pinned_foundation", path / "t_duck_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Simulation:
    """Single-owner 50 Hz policy / 200 Hz physics actor using unchanged foundation functions."""
    def __init__(self, foundation, rl, runtime, seed=30000, clock=time.monotonic):
        self.foundation = load_foundation(Path(foundation))
        self.mj, self.np = self.foundation.mujoco, self.foundation.np
        upstream, policy_path = self.foundation.load_upstream(Path(rl), Path(runtime))
        (self.model, self.data, self.policy, self.controller, self.metadata, self.targets,
         self.initial, self.initial_hash) = self.foundation.make_trial(
            Path(rl), upstream, policy_path, seed, "policy", (0., 0., 0.))
        if self.model.nu != 14:
            raise ValueError("Expected pinned 14-actuator T-Duck, not starter robot")
        self.floor = self.model.geom("floor").id
        self.feet = [self.model.geom(name).id for name in ("left_foot_collision", "right_foot_collision")]
        self.names = self.metadata["joint_names"].split(",")
        self.dofs = [int(self.model.jnt_dofadr[int(self.model.actuator_trnid[i, 0])]) for i in range(self.model.nu)]
        self.lock = threading.RLock()
        self.clock = clock
        self.mode, self.status = "rest", "ready"
        self.paused, self.deadline = True, 0.
        self.warnings = []
        self.frame, self.last_command_id = 0, None
        self.stop_event = threading.Event()
        self.thread = None
        self.worker_heartbeat = self.clock()
        self.failure = None
        self.idle_timeout_s = 60.
        self.last_intent = self.clock()

    def _watchdog(self):
        if self.mode in MOVING and self.clock() >= self.deadline:
            self.mode = "stop"
            self.policy.set_vel_cmd(0., 0., 0.)
            self.warnings = ["Movement lease expired; simulation watchdog cleared twist"]

    def apply(self, command, ttl_ms, command_id):
        with self.lock:
            if command not in COMMANDS:
                return False, "unsupported_command"
            if self.status != "ready" and command not in {"stop", "rest"}:
                return False, "unsafe_state"
            self._watchdog()
            self.mode = command
            self.last_intent = self.clock()
            self.paused = command == "rest" or self.status != "ready" or (command == "stop" and self.paused)
            self.deadline = self.clock() + ttl_ms / 1000.
            self.last_command_id = command_id
            self.policy.set_vel_cmd(*TWISTS[command])
            if self.status == "ready":
                self.warnings = []
            return True, None

    def tick(self):
        with self.lock:
            self.worker_heartbeat = self.clock()
            self._watchdog()
            if not self.paused and self.clock() - self.last_intent >= self.idle_timeout_s:
                self.mode, self.paused = "rest", True
                self.policy.set_vel_cmd(0., 0., 0.)
                self.warnings = ["Owner idle for 60 seconds; simulation paused. Send a deliberate command to resume."]
            if self.paused or self.status != "ready":
                return
            obs = self.policy.get_observations()
            if obs.shape != (61,) or not self.np.isfinite(obs).all():
                raise ValueError("Invalid policy observation")
            action = self.policy.infer()
            if action.shape != (14,) or not self.np.isfinite(action).all():
                raise ValueError("Invalid policy action")
            target = self.policy.default_pose + action
            for _ in range(self.foundation.DECIMATION):
                self._watchdog()
                self.targets.append(target.copy())
                delayed = self.targets.pop(0)
                for name, value in zip(self.controller.actuator, delayed):
                    self.controller.set_q_target(name, value)
                self.data.xfrc_applied[:] = 0.
                self.controller.update()
                self.foundation.advance_physics(self.model, self.data)
                self.frame += 1
                if not self.np.isfinite(self.data.qpos).all() or not self.np.isfinite(self.data.qvel).all():
                    raise ValueError("Non-finite physics state")
                rotation = self.data.xmat[self.policy.trunk_base_id].reshape(3, 3)
                if float(self.data.qpos[2]) < self.foundation.MIN_HEIGHT or rotation[2, 2] < self.foundation.MIN_UPRIGHT:
                    self.status, self.mode, self.paused = "fallen", "stop", True
                    self.policy.set_vel_cmd(0., 0., 0.)
                    self.warnings = ["MuJoCo fall threshold crossed; physics paused. Recovery is unsupported; restart an episode explicitly."]
                    break

    def start(self):
        def run():
            try:
                next_tick = self.clock()
                while not self.stop_event.is_set():
                    self.tick()
                    next_tick += 0.02
                    remaining = next_tick - self.clock()
                    if remaining < -0.1:
                        next_tick = self.clock()  # Do not catch up with unbounded actuator bursts.
                    self.stop_event.wait(max(0., remaining))
            except Exception as exc:
                with self.lock:
                    self.failure = type(exc).__name__
                    self.status, self.mode, self.paused = "fault", "stop", True
                    self.warnings = ["Simulation fault; movement locked"]
                    self.policy.set_vel_cmd(0., 0., 0.)
        self.thread = threading.Thread(target=run, name="tduck-mujoco-safety-loop", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def telemetry(self):
        with self.lock:
            # No invented power/environment/distance readings. Pose comes only from MjData.
            rotation = self.data.xmat[self.policy.trunk_base_id].reshape(3, 3)
            roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
            pitch = math.asin(max(-1., min(1., -float(rotation[2, 0]))))
            yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
            contacts, forces = [False, False], [0., 0.]
            for contact_index, contact in enumerate(self.data.contact):
                pair = {int(contact.geom1), int(contact.geom2)}
                for i, foot in enumerate(self.feet):
                    if pair == {self.floor, foot} and contact.dist <= 0.:
                        contacts[i] = True
                        wrench = self.np.zeros(6)
                        self.mj.mj_contactForce(self.model, self.data, contact_index, wrench)
                        forces[i] += abs(float(wrench[0]))
            speed = float(self.np.linalg.norm(self.data.qvel[:2]))
            motion = self.status if self.status != "ready" else "paused" if self.paused else "moving" if speed > 0.015 else "balancing"
            heartbeat_age = max(0., self.clock() - self.worker_heartbeat)
            status = "fault" if self.thread and (not self.thread.is_alive() or heartbeat_age > 0.5) else self.status
            pose = {"schema_version": 1, "frame_id": self.frame, "simulation_time_s": float(self.data.time),
                    "coordinate_frame": "world_z_up", "position_m": self.data.qpos[:3].tolist(),
                    "quaternion_wxyz": self.data.qpos[3:7].tolist(),
                    "joints": [{"name": n, "position_rad": float(self.data.qpos[q]), "velocity_rad_s": float(self.data.qvel[v])}
                               for n, q, v in zip(self.names, self.policy.joint_qpos_indices, self.dofs)],
                    "links": [{"name": self.model.body(i).name, "position_m": self.data.xpos[i].tolist(),
                               "quaternion_wxyz": self.data.xquat[i].tolist()} for i in range(1, self.model.nbody)]}
            return {"protocol_version": "1.1", "device_id": DEVICE_ID, "simulated": True,
                    "telemetry_source": "mujoco", "software_version": "0.2.0-sim",
                    "battery_percent": None, "battery_voltage": None,
                    "activity": "Resting (simulation paused)" if self.paused and status == "ready" else
                                {"stand": "Standing", "stop": "Stopping / balancing", "forward": "Walking forward",
                                 "left": "Turning left", "right": "Turning right"}.get(self.mode, "Motion locked"),
                    "movement_mode": self.mode, "motion_state": motion, "status": status,
                    "warnings": self.warnings + (["Simulation worker stale; controls must remain locked"] if status == "fault" and self.status != "fault" else []),
                    "roll_deg": math.degrees(roll), "pitch_deg": math.degrees(pitch), "yaw_deg": math.degrees(yaw),
                    "left_contact": contacts[0], "right_contact": contacts[1],
                    "left_contact_force_n": forces[0], "right_contact_force_n": forces[1],
                    "linear_velocity_m_s": self.data.qvel[:3].tolist(), "angular_velocity_rad_s": self.data.qvel[3:6].tolist(),
                    "desired_twist": list(TWISTS[self.mode]), "last_command_id": self.last_command_id,
                    "physics_paused": self.paused, "pose": pose,
                    "sample_monotonic_ns": time.monotonic_ns(), "worker_age_s": heartbeat_age,
                    "unavailable_fields": ["battery_percent", "battery_voltage", "distance_cm", "touch", "camera_available", "temperature_c", "motor_temperature_c"],
                    "synthetic_fields": [],
                    "provenance": {**LOCK, "mujoco_version": self.mj.__version__, "onnxruntime_version": self.foundation.ort.__version__,
                                   "numpy_version": self.np.__version__, "model_actuators": self.model.nu,
                                   "controller": "PR2_CPU_BAM_ONNX", "source": "MuJoCo ground truth, not hardware sensors"}}


class CommandGate:
    """Owner control session + monotonic ordering prevent a late forward from undoing stop."""
    def __init__(self, simulation, audit=None):
        self.sim = simulation
        self.lock = threading.RLock()
        self.session, self.sequence = None, 0
        self.boot_id = str(uuid.uuid4())
        self.acks = OrderedDict()
        self.audit_path = Path(audit) if audit else None

    def audit(self, event):
        if self.audit_path:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a") as out:
                out.write(json.dumps(event, allow_nan=False) + "\n")

    def new_session(self):
        with self.lock:
            self.sim.apply("stop", 100, "session-stop")
            # Remain paused until a deliberate movement or stand command.
            self.sim.apply("rest", 100, "session-rest")
            self.session, self.sequence = str(uuid.uuid4()), 0
            self.acks.clear()
            return {"session_id": self.session, "boot_id": self.boot_id}

    def command(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        identity, command, ttl, session, sequence = (payload.get(k) for k in ("id", "command", "ttl_ms", "session_id", "sequence"))
        if not isinstance(identity, str) or not 1 <= len(identity) <= 128 or command not in COMMANDS:
            raise ValueError("Invalid command or ID")
        if type(ttl) is not int or not 100 <= ttl <= 1000 or type(sequence) is not int or not 1 <= sequence <= 2**53:
            raise ValueError("Invalid movement lease or sequence")
        with self.lock:
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if session != self.session or self.session is None:
                return {"id": identity, "command": command, "accepted": False, "status": "rejected", "reason": "invalid_session"}
            if identity in self.acks:
                old_fingerprint, ack = self.acks[identity]
                if fingerprint != old_fingerprint:
                    raise ValueError("ID already used with different content")
                return copy.deepcopy(ack)
            if sequence <= self.sequence:
                return {"id": identity, "command": command, "accepted": False, "status": "rejected", "reason": "stale_sequence"}
            self.sequence = sequence
            with getattr(self.sim, "lock", contextlib.nullcontext()):
                before = self.sim.telemetry()
                accepted, reason = self.sim.apply(command, ttl, identity)
            ack = {"id": identity, "command": command, "accepted": accepted, "status": "applied" if accepted else "rejected",
                   "sequence": sequence, "applied_frame_id": before["pose"]["frame_id"]}
            if reason:
                ack["reason"] = reason
            self.acks[identity] = fingerprint, ack
            if len(self.acks) > 1024:
                self.acks.popitem(last=False)
            self.audit({"event": "command", **ack, "position_before_m": before["pose"]["position_m"],
                        "simulation_time_s": before["pose"]["simulation_time_s"]})
            return ack

    def telemetry(self):
        snapshot = self.sim.telemetry()
        snapshot["boot_id"] = self.boot_id
        self.audit({"event": "telemetry", "frame_id": snapshot["pose"]["frame_id"],
                    "simulation_time_s": snapshot["pose"]["simulation_time_s"], "position_m": snapshot["pose"]["position_m"],
                    "mode": snapshot["movement_mode"], "last_command_id": snapshot["last_command_id"],
                    "status": snapshot["status"]})
        return snapshot


class BoundedHTTPServer(ThreadingHTTPServer):
    """Bound public request concurrency; slow/unauthenticated clients cannot spawn unlimited threads."""
    daemon_threads = True
    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args, **kwargs)
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(1.)
        if getattr(self, "tls_context", None) is not None:
            connection = self.tls_context.wrap_socket(connection, server_side=True, do_handshake_on_connect=False)
        return connection, address
    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def make_server(host, port, token, gate, cert=None, key=None, *, edge_https=False):
    if len(token) < 24:
        raise ValueError("Provide a random owner token with at least 24 characters")
    if edge_https and os.environ.get("T_DUCK_EDGE_HTTPS") != "trusted-provider-edge-only":
        raise ValueError("Edge HTTP requires an explicit trusted TLS-terminating provider boundary")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def reply(self, code, value):
            body = json.dumps(value, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        def authorized(self):
            # In edge mode this header is trusted ONLY because the selected provider must
            # overwrite it and make this listener unreachable except through its TLS edge.
            if edge_https and self.headers.get("X-Forwarded-Proto") != "https":
                self.reply(403, {"error": "https_required"})
                return False
            try:
                valid = hmac.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + token).encode())
            except (TypeError, ValueError):
                valid = False
            if not valid:
                self.reply(401, {"error": "unauthorized"})
            return valid
        def body(self):
            n = int(self.headers.get("Content-Length", "0"))
            if not 0 < n <= 4096:
                raise ValueError("Request body too large or empty")
            self.connection.settimeout(0.8)
            return json.loads(self.rfile.read(n))
        def do_GET(self):
            if self.path == "/healthz":
                # Liveness only: no telemetry, session, motion, tokens or idle renewal.
                worker = getattr(gate.sim, "thread", None)
                healthy = worker is None or (worker.is_alive() and gate.sim.clock() - gate.sim.worker_heartbeat < .5)
                self.reply(200 if healthy else 503, {"ready": healthy})
                return
            if not self.authorized():
                return
            if self.path == "/v1/capabilities":
                self.reply(200, {"protocol_version": "1.1", "device_id": DEVICE_ID, "simulated": True,
                                 "telemetry_source": "mujoco", "commands": list(COMMANDS),
                                 "ordered_commands": True, "boot_id": gate.boot_id, "max_movement_lease_ms": 1000,
                                 "ota": False, "ble": False, "pose_schema_version": 1})
            elif self.path == "/v1/telemetry":
                self.reply(200, gate.telemetry())
            else:
                self.reply(404, {"error": "not_found"})
        def do_POST(self):
            if not self.authorized():
                return
            try:
                payload = self.body()
                if self.path == "/v1/session":
                    if payload != {"purpose": "companion_control"}:
                        raise ValueError("Invalid session purpose")
                    self.reply(200, gate.new_session())
                elif self.path == "/v1/commands":
                    self.reply(200, gate.command(payload))
                else:
                    self.reply(404, {"error": "not_found"})
            except (ValueError, UnicodeError):
                self.reply(400, {"error": "invalid_request"})
            except (BrokenPipeError, ConnectionError, TimeoutError):
                pass
    server = BoundedHTTPServer((host, port), Handler)
    if not edge_https:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
        server.tls_context = context
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foundation-source", type=Path, required=True)
    parser.add_argument("--rl-source", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    parser.add_argument("--edge-https", action="store_true", help="Only behind a trusted managed HTTPS edge; never a direct public HTTP server")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    simulation = Simulation(args.foundation_source, args.rl_source, args.runtime_source)
    gate = CommandGate(simulation, args.audit)
    server = make_server(args.host, args.port, os.environ.get("T_DUCK_TOKEN", ""), gate, args.cert, args.key, edge_https=args.edge_https)
    simulation.start()
    import signal
    def shutdown(*_):
        simulation.apply("rest", 100, "shutdown-rest")
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    print("T-Duck MuJoCo bridge ready (TLS boundary configured; actual simulation state; no hardware)", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        simulation.close()

if __name__ == "__main__":
    main()
