"""One fresh, complete holdout of the frozen exploratory robustness protocol."""
import argparse
import csv
import json
from pathlib import Path
import time

import t_duck_robustness as suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rl-source", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    development = json.loads(args.development_report.read_text())
    if args.output.exists():
        parser.error("Refusing to overwrite evidence")
    if development["status"] != "completed" or development["trials"] != 180:
        parser.error("Complete development batch required")
    if development["evaluator_sha256"] != suite.foundation.sha256(suite.__file__):
        parser.error("Robustness evaluator changed after development")
    if development["cases"] != suite.cases():
        parser.error("Scenario selection changed after development")
    if suite.foundation.sha256(suite.foundation.__file__) != suite.FOUNDATION_SHA256:
        parser.error("Pinned foundation changed")
    seeds = list(range(50000, 50010))
    if set(seeds) & set(development["seeds"]):
        parser.error("Holdout seed overlap")
    upstream, policy_path = suite.foundation.load_upstream(args.rl_source.resolve(), args.runtime_source.resolve())
    args.output.mkdir(parents=True)
    rows = []
    started = time.process_time()
    with (args.output / "trials.jsonl").open("w") as output:
        for case in development["cases"]:
            for seed in seeds:
                pair = []
                for mode in ("policy", "fixed_pose"):
                    if time.process_time()-started > 600:
                        raise RuntimeError("600 CPU second budget exceeded; partial JSONL retained")
                    trial = suite.run_trial(args.rl_source.resolve(), upstream, policy_path, seed, case, mode)
                    output.write(json.dumps(trial)+"\n")
                    output.flush()
                    pair.append(trial["metrics"])
                    rows.append(trial["metrics"])
                if pair[0]["initial_sha256"] != pair[1]["initial_sha256"]:
                    raise AssertionError("Unpaired initial conditions")
            print(case["name"], "holdout complete", flush=True)
    with (args.output / "trials.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(development)
    report.update(stage="fresh_holdout_no_controller_tuning", trials=len(rows), seeds=seeds,
                  elapsed_cpu_s=time.process_time()-started,
                  development_report_sha256=suite.foundation.sha256(args.development_report),
                  holdout_runner_sha256=suite.foundation.sha256(__file__),
                  limitations=["Ten seeds per scenario; sampled conditions only",
                               "Feet-only collision, CPU/runtime/sensing limitations inherited",
                               "Peak tilt samples after physics steps; initial pose separately recorded",
                               "No controller tuning/training or Companion lock change"])
    (args.output / "report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("status", "stage", "trials", "elapsed_cpu_s")}))


if __name__ == "__main__":
    main()
