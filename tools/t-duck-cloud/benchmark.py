"""Measure real pinned MuJoCo CPU/memory/telemetry. Run on target host before accepting it."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "t-duck-bridge"))
from bridge import Simulation


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["foundation", "rl", "runtime"]:
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    with contextlib.redirect_stdout(io.StringIO()):
        start = time.perf_counter()
        sim = Simulation(args.foundation, args.rl, args.runtime)
        load = time.perf_counter() - start
        sim.apply("stand", 1000, "resource-benchmark")
        samples = []; cpu = time.process_time()
        for _ in range(100):
            tick = time.perf_counter(); sim.tick(); samples.append(time.perf_counter() - tick)
        cpu = time.process_time() - cpu
        t = sim.telemetry()
    size = len(json.dumps(t).encode())
    print(json.dumps({"load_wall_s": load, "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "tick_wall_mean_s": sum(samples) / len(samples), "tick_wall_p95_s": sorted(samples)[94],
        "realtime_cpu_fraction": cpu / 2, "telemetry_bytes": size,
        "telemetry_mib_per_hour_at_5hz": size * 5 * 3600 / 1024**2, "status": t["status"],
        "hardware": os.uname().machine, "provenance": t["provenance"],
        "scope": "This host only; not public-endpoint, provider-quota, or phone connectivity evidence"}, indent=2))

if __name__ == "__main__": main()
