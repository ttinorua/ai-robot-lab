"""CPU-only, pinned-source T-Duck evaluation; no training or asset redistribution.

Uses Luwu Dynamics' Apache-2.0 inference helper and vendored Rhoban BAM.
Supply separate, unmodified upstream checkouts; see docs/T_DUCK_PROGRESS.md.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time
from types import SimpleNamespace

import mujoco
import numpy as np
import onnxruntime as ort

RL_REV = "725ed0c75a73988adc4f9ede280d2d340664e997"
RUNTIME_REV = "8837d5a3bc7cf3746f6da2b55c7b9191026b9838"
POLICY_SHA256 = "57cdebf36e7fa23116270dec96f013a6a64511f37311d322443f5297bdc3d6db"
DT = 0.005
DECIMATION = 4
DURATION = 10.0
MIN_UPRIGHT = math.cos(math.radians(30))
MIN_HEIGHT = 0.09
MIN_FORWARD = 0.20
HOLDOUT_SEED_START = 30000  # 20000–20009 retired after derived-state audit
ROBOT_DIR = "src/mjlab_microduck/robot/xgoduck"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def advance_physics(model, data):
    """Refresh derived state after integration before sensing/gates/logging."""
    mujoco.mj_step(model, data)
    mujoco.mj_forward(model, data)


def verify_checkout(path, revision):
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if actual != revision:
        raise ValueError(f"Wrong upstream revision: {actual}; expected {revision}")
    subprocess.run(["git", "-C", str(path), "diff", "--quiet", "HEAD", "--"], check=True)


def load_upstream(rl, runtime):
    verify_checkout(rl, RL_REV)
    verify_checkout(runtime, RUNTIME_REV)
    policy_path = runtime / "python/xgoduck_walk.onnx"
    if sha256(policy_path) != POLICY_SHA256:
        raise ValueError("Walking policy hash mismatch")
    sys.path.insert(0, str(rl / "vendor/bam"))
    spec = importlib.util.spec_from_file_location("xgoduck_inference", rl / "scripts/infer_policy.py")
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    def cpu_session(path):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return ort.InferenceSession(path, sess_options=options, providers=["CPUExecutionProvider"])
    upstream.ort = SimpleNamespace(InferenceSession=cpu_session)
    return upstream, policy_path


def validate_metadata(policy, model):
    session = policy.ort_session
    if session.get_inputs()[0].shape != [1, 61] or session.get_outputs()[0].shape != [1, 14]:
        raise ValueError("Policy must have observation [1,61] and action [1,14]")
    metadata = session.get_modelmeta().custom_metadata_map
    names = metadata["joint_names"].split(",")
    actual = [model.joint(int(model.actuator_trnid[i, 0])).name for i in range(model.nu)]
    if names != actual:
        raise ValueError(f"Actuator order mismatch: {actual}")
    if metadata["command_names"] != "twist,head_pose,body_pose":
        raise ValueError("Unsupported command layout")
    home = np.array([float(v) for v in metadata["default_joint_pos"].split(",")], dtype=np.float32)
    if home.shape != (14,) or not np.isfinite(home).all():
        raise ValueError("Invalid home pose")
    if float(metadata["action_scale"]) != 1.0:
        raise ValueError("Unsupported action scale")
    policy.default_pose = home
    return metadata


def make_trial(rl, upstream, policy_path, seed, mode, command):
    from bam.model import load_model
    from bam.mujoco import MujocoController

    spec = mujoco.MjSpec.from_file(str(rl / ROBOT_DIR / "scene_walk.xml"))
    # Match upstream CPU BAM testbench: BAM supplies torque, not companion PD.
    for actuator in spec.actuators:
        actuator.set_to_motor()
        actuator.forcelimited = False
        actuator.ctrllimited = False
    model = spec.compile()
    model.opt.timestep = DT
    data = mujoco.MjData(model)
    with contextlib.redirect_stdout(io.StringIO()):
        policy = upstream.PolicyInference(model, data, walking_onnx_path=str(policy_path),
                                         new_cmd_obs=True, use_projected_gravity=True)
        metadata = validate_metadata(policy, model)
        policy.set_vel_cmd(*command)
    bam = load_model(str(rl / ROBOT_DIR / "params/1910_m6.json"))
    bam.actuator.kp = 5.0
    bam.actuator.vin = 7.7
    controller = MujocoController(bam, [model.actuator(i).name for i in range(model.nu)],
                                 model, data, vin_drop_gain=0.1, vin_min=7.0)
    rng = np.random.default_rng(seed)
    # Same draws for the policy and fixed-pose comparator, including latency.
    tilt = rng.uniform(-math.radians(2), math.radians(2), 2)
    roll = np.array([math.cos(tilt[0] / 2), math.sin(tilt[0] / 2), 0., 0.])
    pitch = np.array([math.cos(tilt[1] / 2), 0., math.sin(tilt[1] / 2), 0.])
    quat = np.empty(4)
    mujoco.mju_mulQuat(quat, roll, pitch)
    data.qpos[2] = 0.139439  # XGODUCK_WALK_STAND_Z at pinned source
    data.qpos[3:7] = quat
    data.qpos[policy.joint_qpos_indices] = policy.default_pose + rng.uniform(-0.01, 0.01, 14)
    data.qvel[:] = rng.normal(0., 0.015, model.nv)
    lag = int(rng.integers(3, 7))  # 15–30 ms, upstream Walk configuration
    mujoco.mj_forward(model, data)
    controller.reset(data.qpos)
    bam.actuator.q_target_smooth = data.qpos[policy.joint_qpos_indices].copy()
    # MujocoController has no built-in command-delay buffer.
    targets = [policy.default_pose.copy() for _ in range(lag)]
    initial = {"qpos": data.qpos.tolist(), "qvel": data.qvel.tolist(), "lag": lag}
    initial_hash = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()
    return model, data, policy, controller, metadata, targets, initial, initial_hash


def run_trial(rl, upstream, policy_path, seed, case, mode):
    commands = {"stand": (0., 0., 0.), "forward": (0.2, 0., 0.),
                "left": (0.1, 0., 0.5), "right": (0.1, 0., -0.5),
                "push": (0., 0., 0.)}
    model, data, policy, controller, metadata, targets, initial, initial_hash = make_trial(
        rl, upstream, policy_path, seed, mode, commands[case])
    start_xy = data.qpos[:2].copy()
    floor = model.geom("floor").id
    feet = [model.geom(n).id for n in ("left_foot_collision", "right_foot_collision")]
    sites = [model.site(n).id for n in ("left_foot", "right_foot")]
    trace, contacts = [], {"left_only": 0, "right_only": 0, "both": 0, "neither": 0}
    min_up, min_height, impulse, path_length = 1., float(data.qpos[2]), 0., 0.
    max_foot_lift = [0., 0.]
    previous_xy = start_xy.copy()
    yaw = previous_yaw = 0.
    fallen = False
    for step in range(round(DURATION / (DT * DECIMATION))):
        obs = policy.get_observations()
        if obs.shape != (61,) or not np.isfinite(obs).all():
            raise ValueError("Non-finite or malformed observation")
        action = policy.infer() if mode == "policy" else np.zeros(14, dtype=np.float32)
        if action.shape != (14,) or not np.isfinite(action).all():
            raise ValueError("Non-finite or malformed action")
        target = policy.default_pose + action
        for inner in range(DECIMATION):
            targets.append(target.copy())
            delayed = targets.pop(0)
            for name, value in zip(controller.actuator, delayed):
                controller.set_q_target(name, value)
            data.xfrc_applied[:] = 0.
            if case == "push" and 600 <= step * DECIMATION + inner < 620:
                data.xfrc_applied[policy.trunk_base_id, 0] = 0.5  # 0.05 N s
                impulse += 0.5 * DT
            controller.update()
            advance_physics(model, data)
            up = float(data.xmat[policy.trunk_base_id].reshape(3, 3)[2, 2])
            height = float(data.qpos[2])
            min_up, min_height = min(min_up, up), min(min_height, height)
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                raise ValueError("Simulation became non-finite")
            xy = data.qpos[:2].copy()
            path_length += float(np.linalg.norm(xy - previous_xy))
            previous_xy = xy
            # Accumulate unwrapped world yaw, not quaternion component changes.
            rotation = data.xmat[policy.trunk_base_id].reshape(3, 3)
            current_yaw = math.atan2(rotation[1, 0], rotation[0, 0])
            yaw += math.atan2(math.sin(current_yaw - previous_yaw), math.cos(current_yaw - previous_yaw))
            previous_yaw = current_yaw
            touch = [False, False]
            for contact in data.contact:
                pair = {int(contact.geom1), int(contact.geom2)}
                for index, foot in enumerate(feet):
                    touch[index] |= pair == {floor, foot} and contact.dist <= 0.
            key = ("both" if all(touch) else "left_only" if touch[0] else "right_only" if touch[1] else "neither")
            contacts[key] += 1
            for i, site in enumerate(sites):
                max_foot_lift[i] = max(max_foot_lift[i], float(data.site_xpos[site, 2]))
            if height < MIN_HEIGHT or up < MIN_UPRIGHT:
                fallen = True
                break
        if step % 10 == 0 or fallen or step == 499:
            trace.append({"seed": seed, "case": case, "controller": mode, "time_s": float(data.time),
                          "x_m": float(data.qpos[0]), "y_m": float(data.qpos[1]), "z_m": float(data.qpos[2]),
                          "upright_cos": up, "yaw_rad": yaw, "action_l2": float(np.linalg.norm(action)),
                          "left_foot_z_m": float(data.site_xpos[sites[0], 2]),
                          "right_foot_z_m": float(data.site_xpos[sites[1], 2])})
        if fallen:
            break
    displacement = data.qpos[:2] - start_xy
    row = {"seed": seed, "case": case, "controller": mode, "survived": not fallen,
           "survival_s": round(float(data.time), 6), "forward_m": float(displacement[0]),
           "lateral_m": float(displacement[1]), "path_m": path_length, "yaw_rad": yaw,
           "min_upright_cos": min_up, "min_height_m": min_height,
           "push_impulse_Ns": impulse, "initial_state_sha256": initial_hash,
           "latency_steps": initial["lag"], **contacts,
           "max_left_foot_z_m": max_foot_lift[0], "max_right_foot_z_m": max_foot_lift[1]}
    return row, trace, initial, metadata


def acceptance(rows):
    selected = [r for r in rows if r["controller"] == "policy" and r["case"] in ("stand", "forward")]
    seeds = [{r["seed"] for r in selected if r["case"] == case} for case in ("stand", "forward")]
    return (len(selected) == 20 and len(seeds[0]) == 10 and seeds[0] == seeds[1]
            and all(r["survived"] and r["survival_s"] >= DURATION
                    and (r["case"] != "forward" or r["forward_m"] >= MIN_FORWARD) for r in selected))


def main():
    started_wall, started_cpu = time.monotonic(), time.process_time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rl-source", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("development", "holdout"), default="development")
    parser.add_argument("--development-report", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output directory already exists; preserve prior results")
    if args.stage == "holdout":
        if not args.development_report:
            parser.error("Holdout requires a passing development report")
        dev = json.loads(args.development_report.read_text())
        if not dev["acceptance_passed"] or dev["rl_revision"] != RL_REV or dev["policy_sha256"] != POLICY_SHA256:
            parser.error("Development did not qualify this model/policy for holdout")
        if dev.get("evaluator_sha256") != sha256(__file__):
            parser.error("Evaluator changed since development; run development first")
    upstream, policy_path = load_upstream(args.rl_source.resolve(), args.runtime_source.resolve())
    cases = ("stand", "forward", "left", "right", "push") if args.stage == "development" else ("stand", "forward")
    seeds = range(10000, 10010) if args.stage == "development" else range(HOLDOUT_SEED_START, HOLDOUT_SEED_START + 10)
    rows, trace, initial_states = [], [], {}
    for case in cases:
        for seed in seeds:
            for mode in ("policy", "fixed_pose"):
                row, samples, initial, metadata = run_trial(args.rl_source.resolve(), upstream, policy_path, seed, case, mode)
                rows.append(row)
                trace.extend(samples)
                initial_states[f"{case}/{seed}/{mode}"] = initial
                if time.process_time() - started_cpu > 600:
                    raise RuntimeError("600 CPU second evaluation budget exhausted")
            if rows[-1]["initial_state_sha256"] != rows[-2]["initial_state_sha256"]:
                raise AssertionError("Unpaired comparator initialization")
    report = {"stage": args.stage, "acceptance_passed": acceptance(rows), "rl_revision": RL_REV,
              "runtime_revision": RUNTIME_REV, "policy_sha256": POLICY_SHA256, "policy_metadata": metadata,
              "evaluator_sha256": sha256(__file__),
              "elapsed_wall_s": time.monotonic() - started_wall,
              "elapsed_cpu_s": time.process_time() - started_cpu,
              "development_report_sha256": sha256(args.development_report) if args.development_report else None,
              "runtime": {"python": platform.python_version(), "mujoco": mujoco.__version__,
                          "onnxruntime": ort.__version__, "numpy": np.__version__},
              "protocol": {"duration_s": DURATION, "physics_dt_s": DT, "policy_hz": 50,
                           "min_height_m": MIN_HEIGHT, "min_upright_cos": MIN_UPRIGHT,
                           "min_forward_m": MIN_FORWARD, "roll_pitch_deg": [-2, 2],
                           "joint_offset_rad": [-0.01, 0.01], "initial_velocity_std": 0.015,
                           "bam_kp": 5., "voltage": 7.7, "sag_gain": 0.1, "minimum_voltage": 7.,
                           "delay_physics_steps": [3, 6], "holdout_seeds": [HOLDOUT_SEED_START, HOLDOUT_SEED_START + 9]},
              "limitations": ["CPU BAM MujocoController is not the trained mjlab actuator implementation",
                              "Original Walk model has feet-only ground collision; non-foot collisions not evaluated",
                              "ONNX metadata home angles are rounded to 0.001 rad",
                              "Small initial randomization; no hardware or broad robustness claim",
                              "Asset redistribution rights remain unresolved; assets are external checkouts only"],
              "initial_states": initial_states, "trials": rows}
    args.output.mkdir(parents=True)
    for name, records in (("trials.csv", rows), ("trace.csv", trace)):
        with (args.output / name).open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"acceptance_passed": report["acceptance_passed"], "trials": len(rows),
                      "output": str(args.output)}))
    return 0 if report["acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
