import importlib.util
import json
import math
import os
from pathlib import Path
import threading
import time
import unittest

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("bridge.py"))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class StubSimulation:
    def __init__(self): self.commands = []
    def apply(self, command, ttl, identity):
        self.commands.append((command, ttl, identity)); return True, None
    def telemetry(self):
        return {"pose": {"frame_id": 42, "position_m": [0., 0., .14], "simulation_time_s": .2}, "last_command_id": "test", "movement_mode": "stand", "status": "ready"}

class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.sim = StubSimulation(); self.gate = bridge.CommandGate(self.sim)
        self.session = self.gate.new_session()["session_id"]
    def command(self, identity="one", command="forward", sequence=1, session=None, ttl=500):
        return {"id": identity, "command": command, "sequence": sequence, "session_id": session or self.session, "ttl_ms": ttl}
    def test_late_forward_cannot_undo_stop(self):
        self.assertTrue(self.gate.command(self.command("stop", "stop", 2))["accepted"])
        self.assertFalse(self.gate.command(self.command())["accepted"])
        self.assertEqual(self.sim.commands[-1][0], "stop")
    def test_duplicate_never_renews_lease(self):
        one = self.gate.command(self.command()); n = len(self.sim.commands)
        self.assertEqual(one, self.gate.command(self.command()))
        self.assertEqual(n, len(self.sim.commands))
    def test_conflicting_duplicate_rejected(self):
        self.gate.command(self.command())
        with self.assertRaises(ValueError): self.gate.command(self.command(command="left"))
    def test_reconnect_retires_old_session_and_stops(self):
        old = self.session; self.gate.new_session()
        self.assertFalse(self.gate.command(self.command(session=old))["accepted"])
        self.assertEqual(self.sim.commands[-1][0], "rest")
    def test_invalid_commands_and_leases(self):
        for c in [self.command(command="recover"), self.command(command="raw_motor"), self.command(ttl=0), self.command(sequence=True), self.command(ttl=1001)]:
            with self.assertRaises(ValueError): self.gate.command(c)

@unittest.skipUnless(os.environ.get("TC02_FOUNDATION"), "Pinned external simulation sources required")
class ActualMuJoCoTests(unittest.TestCase):
    def make_sim(self, clock=time.monotonic):
        return bridge.Simulation(os.environ["TC02_FOUNDATION"], os.environ["TC02_RL"], os.environ["TC02_RUNTIME"], clock=clock)
    def run_motion(self, command, frames=50):
        sim = self.make_sim(); before = sim.telemetry()
        sim.apply(command, 1000, "actual-physics-test")
        for _ in range(frames): sim.tick()
        return before, sim.telemetry()
    def test_actual_forward_outperforms_identical_standing_state(self):
        before, after = self.run_motion("forward")
        sb, sa = self.run_motion("stand")
        dx = after["pose"]["position_m"][0] - before["pose"]["position_m"][0]
        baseline = sa["pose"]["position_m"][0] - sb["pose"]["position_m"][0]
        self.assertGreater(dx, .04)
        self.assertGreater(dx, baseline + .03)
        self.assertEqual(after["provenance"]["model_actuators"], 14)
        self.assertEqual(after["status"], "ready")
        self.assertEqual(after["telemetry_source"], "mujoco")
        self.assertIsNone(after["battery_percent"])
        self.assertNotIn("distance_cm", after)
    def test_left_and_right_change_actual_yaw_in_opposite_directions(self):
        for command, sign in [("left", 1), ("right", -1)]:
            before, after = self.run_motion(command)
            self.assertGreater((after["yaw_deg"] - before["yaw_deg"]) * sign, 5.)
            self.assertEqual(after["status"], "ready")
    def test_pose_matches_mjdata_and_contacts_match_collision_pairs(self):
        sim = self.make_sim(); sim.apply("stand", 1000, "pose-test")
        for _ in range(20): sim.tick()
        t = sim.telemetry()
        self.assertEqual(t["pose"]["position_m"], sim.data.qpos[:3].tolist())
        self.assertEqual(t["pose"]["quaternion_wxyz"], sim.data.qpos[3:7].tolist())
        self.assertEqual(len(t["pose"]["joints"]), 14)
        self.assertEqual(t["pose"]["joints"][0]["position_rad"], float(sim.data.qpos[sim.policy.joint_qpos_indices[0]]))
        self.assertGreater(t["pose"]["frame_id"], 0)
        for i, side in enumerate(["left", "right"]):
            expected = any({int(c.geom1), int(c.geom2)} == {sim.floor, sim.feet[i]} and c.dist <= 0 for c in sim.data.contact)
            self.assertEqual(t[side + "_contact"], expected)
            self.assertGreaterEqual(t[side + "_contact_force_n"], 0)
    def test_rest_pauses_actual_simulation_without_reset(self):
        sim = self.make_sim(); sim.apply("stand", 1000, "stand")
        for _ in range(10): sim.tick()
        sim.apply("rest", 1000, "rest"); before = sim.telemetry()
        for _ in range(10): sim.tick()
        after = sim.telemetry()
        self.assertEqual(before["pose"], after["pose"])
        sim.apply("stop", 1000, "stop"); sim.tick()
        self.assertEqual(after["pose"], sim.telemetry()["pose"])
    def test_real_wall_clock_watchdog_without_network_traffic(self):
        sim = self.make_sim(); sim.start()
        try:
            sim.apply("forward", 100, "watchdog")
            time.sleep(.28)
            t = sim.telemetry()
            self.assertEqual(t["movement_mode"], "stop")
            self.assertEqual(t["desired_twist"], [0., 0., 0.])
            self.assertTrue(any("lease expired" in x for x in t["warnings"]))
        finally: sim.close()
    def test_fall_latches_and_rejects_more_motion(self):
        sim = self.make_sim(); sim.data.qpos[2] = .02; sim.mj.mj_forward(sim.model, sim.data)
        sim.apply("stand", 1000, "fall-check"); sim.tick()
        self.assertEqual(sim.status, "fallen")
        self.assertFalse(sim.apply("forward", 1000, "unsafe")[0])
        sim.apply("stop", 1000, "safe")
        self.assertEqual(sim.telemetry()["status"], "fallen")
        self.assertTrue(sim.paused)


@unittest.skipUnless(os.environ.get("TC02_FOUNDATION"), "Pinned external simulation sources required")
class ActualHTTPSTests(unittest.TestCase):
    def test_verified_tls_command_ack_and_actual_physics_roundtrip(self):
        import ssl, tempfile, subprocess, urllib.request, urllib.error
        sim = bridge.Simulation(os.environ["TC02_FOUNDATION"], os.environ["TC02_RL"], os.environ["TC02_RUNTIME"])
        gate = bridge.CommandGate(sim)
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as work:
            cert, key = Path(work)/"ca.pem", Path(work)/"key.pem"
            fixture = root / "apps/t-duck-companion/app/src/test/resources/tls/tduck-simulator-test-only.p12"
            for flags, output in [(["-clcerts", "-nokeys"], cert), (["-nocerts", "-nodes"], key)]:
                subprocess.run(["openssl", "pkcs12", "-in", str(fixture), "-passin", "pass:test-fixture-only", *flags, "-out", str(output)], check=True, capture_output=True)
            token = "public-test-owner-token-not-a-production-credential"
            server = bridge.make_server("127.0.0.1", 0, token, gate, cert, key)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start(); sim.start()
            try:
                base = f"https://localhost:{server.server_address[1]}/v1/"
                context = ssl.create_default_context(cafile=str(cert))
                def request(path, body=None, auth=token):
                    r = urllib.request.Request(base+path, data=json.dumps(body).encode() if body is not None else None,
                        headers={"Authorization": "Bearer "+auth, "Content-Type": "application/json"})
                    with urllib.request.urlopen(r, context=context, timeout=1) as response: return json.load(response)
                with self.assertRaises(urllib.error.HTTPError) as error: request("telemetry", auth="wrong")
                self.assertEqual(error.exception.code, 401)
                self.assertTrue(request("capabilities")["ordered_commands"])
                session = request("session", {"purpose":"companion_control"})["session_id"]
                before = request("telemetry")
                ack = request("commands", {"id":"https-forward", "command":"forward", "sequence":1, "session_id":session, "ttl_ms":500})
                self.assertTrue(ack["accepted"]); self.assertEqual(ack["id"],"https-forward")
                time.sleep(.7)
                after = request("telemetry")
                self.assertEqual(after["telemetry_source"], "mujoco")
                self.assertEqual(after["movement_mode"], "stop")
                self.assertGreater(after["pose"]["position_m"][0] - before["pose"]["position_m"][0], .02)
                self.assertGreater(after["pose"]["frame_id"], before["pose"]["frame_id"])
                self.assertEqual(after["last_command_id"], "https-forward")
                self.assertEqual(after["pose"]["joints"][0]["name"], sim.names[0])
            finally:
                sim.close(); server.shutdown(); server.server_close(); thread.join(timeout=1)

if __name__ == "__main__": unittest.main()
