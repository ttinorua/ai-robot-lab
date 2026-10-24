"""Staging entrypoint. No asset fetch until owner confirms source-use review.

No provider API calls, billing changes, deployment, or credential generation.
Fetches pinned sources into private ephemeral runtime storage, never a published image.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "bridge" if (ROOT / "bridge").is_dir() else ROOT.parent / "t-duck-bridge"
LOCK = json.loads((BRIDGE / "integration-lock.json").read_text())
SOURCES = {
    "foundation": ("https://github.com/ttinorua/ai-robot-lab.git", LOCK["foundation_revision"]),
    "rl": ("https://github.com/LuwuDynamics/xgoduck_rl.git", LOCK["rl_revision"]),
    "runtime": ("https://github.com/LuwuDynamics/xgoduck_runtime_arduino.git", LOCK["runtime_revision"]),
}


def validate_environment(env):
    if env.get("T_DUCK_SOURCE_USE_APPROVED") != "yes":
        raise ValueError("Source-use review not approved; refusing to fetch upstream assets")
    if env.get("T_DUCK_EDGE_HTTPS") != "trusted-provider-edge-only":
        raise ValueError("Explicit trusted HTTPS edge configuration required")
    token = env.get("T_DUCK_TOKEN", "")
    if len(token) < 24 or token.strip() != token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("Supply an owner-managed random token of at least 24 printable characters")
    port = int(env.get("PORT", "10000"))
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid unprivileged listen port")
    return port


def fetch_sources(root):
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, revision) in SOURCES.items():
        target = root / name
        if target.exists():
            raise ValueError("Require fresh ephemeral source storage")
        target.mkdir()
        for args in [["init", "--quiet"], ["remote", "add", "origin", url],
                     ["fetch", "--quiet", "--depth=1", "origin", revision], ["checkout", "--quiet", "--detach", "FETCH_HEAD"]]:
            subprocess.run(["git", "-C", str(target), *args], check=True, timeout=180)
        actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise ValueError("Source revision mismatch")


def main():
    port = validate_environment(os.environ)
    root = Path("/sources")
    fetch_sources(root)
    os.execv(sys.executable, [sys.executable, str(BRIDGE / "bridge.py"),
        "--foundation-source", str(root / "foundation"), "--rl-source", str(root / "rl"),
        "--runtime-source", str(root / "runtime"), "--host", "0.0.0.0", "--port", str(port), "--edge-https"])

if __name__ == "__main__":
    main()
