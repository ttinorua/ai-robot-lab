import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Robot, make_server


class RobotTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.robot = Robot(lambda: self.now)

    def send(self, command="forward", identity="one", ttl=500):
        return self.robot.command({"id": identity, "command": command, "ttl_ms": ttl})

    def test_watchdog_stops_without_client(self):
        self.send()
        self.now += .501
        self.robot.watchdog()
        self.assertEqual(self.robot.mode, "stop")
        self.assertTrue(self.robot.warning)

    def test_retry_does_not_extend_lease(self):
        first = self.send()
        self.now += .4
        self.assertEqual(self.send(), first)
        self.now += .101
        self.assertEqual(self.robot.telemetry()["movement_mode"], "stop")

    def test_conflicting_retry_rejected(self):
        self.send()
        with self.assertRaises(ValueError):
            self.send("right")

    def test_invalid_command_or_lease_rejected(self):
        for command, ttl in [("raw_motor", 500), ("forward", 0), ("forward", 1001), ("forward", True)]:
            with self.subTest(command=command, ttl=ttl), self.assertRaises(ValueError):
                self.send(command, ttl=ttl)

    def test_stop_applies_and_recover_is_capability(self):
        self.send()
        self.send("stop", "two")
        self.assertEqual(self.robot.mode, "stop")
        self.send("recover", "three")
        self.assertEqual(self.robot.mode, "stand")


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token = "test-only-long-random-token-12345"
        cls.server = make_server("127.0.0.1", 0, cls.token)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, payload=None, token=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(self.url + path, data=data,
                          headers={"Authorization": "Bearer " + (token or self.token),
                                   "Content-Type": "application/json"})
        with urlopen(request, timeout=2) as response:
            return json.load(response)

    def test_auth_required_for_telemetry_and_commands(self):
        for path, payload in [("/v1/telemetry", None), ("/v1/commands", {"id": "a", "command": "stop", "ttl_ms": 500})]:
            with self.subTest(path=path), self.assertRaises(HTTPError) as raised:
                self.request(path, payload, "wrong")
            self.assertEqual(raised.exception.code, 401)

    def test_round_trip_capabilities_command_and_telemetry(self):
        capabilities = self.request("/v1/capabilities")
        self.assertTrue(capabilities["simulated"])
        self.assertIn("stop", capabilities["commands"])
        ack = self.request("/v1/commands", {"id": "round-trip", "command": "stand", "ttl_ms": 500})
        self.assertTrue(ack["accepted"])
        self.assertEqual(ack["id"], "round-trip")
        self.assertEqual(self.request("/v1/telemetry")["movement_mode"], "stand")

    def test_invalid_payload_is_400(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/v1/commands", {"id": "bad", "command": "forward", "ttl_ms": 5000})
        self.assertEqual(raised.exception.code, 400)

    def test_missing_route_is_404(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/v2/telemetry")
        self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
