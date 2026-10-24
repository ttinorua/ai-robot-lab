"""Require a non-skipped actual Android/MuJoCo test and correlate it to bridge audit data."""
import base64
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
results = root / "apps/t-duck-companion/app/build/outputs/androidTest-results"
evidence = root / ".tc02/evidence"
evidence.mkdir(parents=True, exist_ok=True)
verified_test = False
for path in results.rglob("TEST-*.xml"):
    suite = ET.parse(path).getroot()
    for case in suite.findall("testcase"):
        if case.attrib.get("classname", "").endswith("MuJoCoRoundTripTest"):
            assert case.find("skipped") is None and case.find("failure") is None and case.find("error") is None
            verified_test = True
assert verified_test, "Actual Android-to-MuJoCo test did not run successfully"
texts = [p.read_text(errors="replace") for p in results.rglob("*MuJoCoRoundTripTest*.txt")]
reports, chunks, expected_chunks = [], {}, None
for text in texts:
    for line in text.splitlines():
        if "TC02_RESULT:" in line:
            reports.append(json.loads(line.split("TC02_RESULT:", 1)[1].strip()))
        match = re.search(r"TC02_SCREEN:\s*(\d+)/(\d+)\s+([A-Za-z0-9+/=]+)", line)
        if match:
            index, total, data = match.groups(); chunks[int(index)] = data; expected_chunks = int(total)
assert reports, "Missing app-side movement evidence"
report = reports[-1]
assert report["verified"] and report["telemetry_source"] == "mujoco"
assert report["forward_displacement_m"] > .015 and report["joints"] == 14
assert report["ui_position_asserted"] and report["ui_time_asserted"] and report["watchdog_observed"]
assert not report["battery_available"]
audit = [json.loads(s) for s in (evidence / "bridge-audit.jsonl").read_text().splitlines()]
command = next(x for x in audit if x["event"] == "command" and x["id"] == report["forward_command_id"])
assert command["accepted"] and command["command"] == "forward"
visible = next(x for x in audit if x["event"] == "telemetry" and x["frame_id"] == report["visible_frame_id"])
assert abs(visible["position_m"][0] - report["visible_x_m"]) < 1e-9
assert abs(visible["simulation_time_s"] - report["visible_simulation_time_s"]) < 1e-9
assert any(x["event"] == "telemetry" and x["last_command_id"] == report["forward_command_id"] and x["mode"] == "forward" for x in audit)
report["bridge_audit_correlated"] = True
report["ui_visible_pose_correlated"] = True
(evidence / "android-mujoco-roundtrip.json").write_text(json.dumps(report, indent=2) + "\n")
assert expected_chunks is not None and len(chunks) == expected_chunks, "Incomplete live UI screenshot"
screenshot = base64.b64decode("".join(chunks[i] for i in range(expected_chunks)))
assert screenshot.startswith(b"\x89PNG\r\n\x1a\n")
(evidence / "android-live-mujoco.png").write_bytes(screenshot)
print(json.dumps(report, indent=2))
