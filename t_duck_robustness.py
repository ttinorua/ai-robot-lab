"""Bounded, exploratory robustness map; leaves Companion's pinned evaluator intact."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import platform
from pathlib import Path
import time

import mujoco
import numpy as np
import onnxruntime as ort
import t_duck_eval as foundation

FOUNDATION_SHA256 = "be98b4a9bb7788e19edecf477afb3d2e535e3a94e4901a7dc27defc6f2f51457"
SEEDS = range(40000, 40005)


def cases():
    result = [dict(name="stand"), dict(name="forward", forward=0.2)]
    for axis, name in ((0, "roll"), (1, "pitch")):
        for sign in (-1, 1):
            result.append(dict(name=f"{name}_{sign*10:+d}deg", tilt_axis=axis, tilt_deg=sign*10))
    for sign in (-1, 1):
        result.append(dict(name=f"velocity_x_{sign:+d}", velocity_x=sign*0.25))
        result.append(dict(name=f"angular_pitch_{sign:+d}", angular_pitch=sign*2.0))
    for impulse in (0.1, 0.2):
        for axis in (0, 1):
            for sign in (-1, 1):
                result.append(dict(name=f"push_{axis}_{sign:+d}_{impulse}",
                                   push_axis=axis, push_impulse=sign*impulse))
    return result


def push_force(case, physics_tick):
    force = np.zeros(3)
    if "push_impulse" in case and 600 <= physics_tick < 620:
        force[case["push_axis"]] = case["push_impulse"] / (20 * foundation.DT)
    return force


def run_trial(rl, upstream, policy_path, seed, case, mode):
    model, data, policy, controller, _, targets, initial, _ = foundation.make_trial(
        rl, upstream, policy_path, seed, mode, (case.get("forward", 0.), 0., 0.))
    if "tilt_deg" in case:
        angle = math.radians(case["tilt_deg"])
        delta = np.zeros(4)
        delta[0] = math.cos(angle/2)
        delta[case["tilt_axis"]+1] = math.sin(angle/2)
        quat = np.empty(4)
        mujoco.mju_mulQuat(quat, delta, data.qpos[3:7].copy())
        data.qpos[3:7] = quat
    data.qvel[0] += case.get("velocity_x", 0.)
    data.qvel[4] += case.get("angular_pitch", 0.)
    mujoco.mj_forward(model, data)
    floor = model.geom("floor").id
    penetration = min([0.] + [float(c.dist) for c in data.contact if floor in (c.geom1, c.geom2)])
    # Tilt must not create an initial interpenetration impulse. Same lift in each pair.
    clearance_lift = -penetration + 0.001 if penetration < 0 else 0.
    data.qpos[2] += clearance_lift
    mujoco.mj_forward(model, data)
    if any(c.dist < -1e-8 for c in data.contact if floor in (c.geom1, c.geom2)):
        raise ValueError("Initial floor interpenetration persists")
    controller.reset(data.qpos)
    controller.model.actuator.q_target_smooth = data.qpos[policy.joint_qpos_indices].copy()
    initial = dict(qpos=data.qpos.tolist(), qvel=data.qvel.tolist(), lag=initial["lag"])
    initial_hash = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()
    impulse = np.zeros(3)
    event_end = 3.1 if "push_impulse" in case else 0.
    band_since = recovery_s = None
    peak_tilt = 0.
    applied_ticks = 0
    fallen = False
    start_xy = data.qpos[:2].copy()
    velocity_before = velocity_after = None
    foot_ids = {model.geom("left_foot_collision").id, model.geom("right_foot_collision").id}
    single_support_ticks = 0
    for tick in range(2000):
        if tick % foundation.DECIMATION == 0:
            obs = policy.get_observations()
            if obs.shape != (61,) or not np.isfinite(obs).all():
                raise ValueError("Invalid policy observation")
            action = policy.infer() if mode == "policy" else np.zeros(14)
            if action.shape != (14,) or not np.isfinite(action).all():
                raise ValueError("Invalid action")
            target = policy.default_pose + action
        targets.append(target.copy())
        delayed = targets.pop(0)
        for name, value in zip(controller.actuator, delayed):
            controller.set_q_target(name, value)
        data.xfrc_applied[:] = 0.
        data.xfrc_applied[policy.trunk_base_id, :3] = push_force(case, tick)
        applied_force = data.xfrc_applied[policy.trunk_base_id, :3].copy()
        if tick == 600:
            velocity_before = data.qvel[:3].copy().tolist()
        impulse += applied_force * foundation.DT
        applied_ticks += int(np.any(applied_force))
        controller.update()
        foundation.advance_physics(model, data)
        if tick == 619:
            velocity_after = data.qvel[:3].copy().tolist()
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise ValueError("Non-finite simulation state")
        up = float(data.xmat[policy.trunk_base_id].reshape(3, 3)[2, 2])
        tilt = math.degrees(math.acos(float(np.clip(up, -1., 1.))))
        peak_tilt = max(peak_tilt, tilt)
        fallen = up < foundation.MIN_UPRIGHT or data.qpos[2] < foundation.MIN_HEIGHT
        touching = {int(c.geom1 if c.geom2 == floor else c.geom2) for c in data.contact
                    if floor in (c.geom1, c.geom2) and c.dist <= 0.}
        single_support_ticks += int(len(touching & foot_ids) == 1)
        settled = (not fallen and tilt <= 5. and np.linalg.norm(data.qvel[3:6]) <= .5
                   and np.linalg.norm(data.qvel[:2]) <= .05)
        if data.time >= event_end - 1e-9:
            if settled:
                if band_since is None:
                    band_since = float(data.time)
                if recovery_s is None and data.time - band_since >= 1.-1e-9:
                    recovery_s = float(data.time - event_end)
            else:
                band_since = None
        if fallen:
            break
    expected = np.zeros(3)
    if "push_impulse" in case:
        expected[case["push_axis"]] = case["push_impulse"]
    fully_applied = bool(np.allclose(impulse, expected, rtol=0, atol=1e-12))
    final_settled = (not fallen and band_since is not None and data.time - band_since >= 1.-1e-9)
    metrics = dict(case=case["name"], seed=seed, controller=mode, survived=not fallen,
                   survival_s=round(float(data.time), 6), peak_tilt_deg=peak_tilt,
                   forward_m=float(data.qpos[0]-start_xy[0]), lateral_m=float(data.qpos[1]-start_xy[1]),
                   clearance_lift_m=clearance_lift, latency_steps=initial["lag"],
                   initial_sha256=initial_hash, recovery_confirmed_s=recovery_s if not case.get("forward") else None,
                   final_settled=bool(final_settled) if not case.get("forward") else None,
                   impulse_x_Ns=float(impulse[0]), impulse_y_Ns=float(impulse[1]),
                   push_ticks=applied_ticks, disturbance_fully_applied=fully_applied,
                   single_support_ticks=single_support_ticks)
    return dict(metrics=metrics, initial=initial, case_spec=case,
                velocity_before_push=velocity_before, velocity_after_push=velocity_after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rl-source", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite existing evidence")
    if foundation.sha256(foundation.__file__) != FOUNDATION_SHA256:
        parser.error("Companion-pinned foundation changed")
    upstream, policy_path = foundation.load_upstream(args.rl_source.resolve(), args.runtime_source.resolve())
    args.output.mkdir(parents=True)
    start = time.process_time()
    rows = []
    with (args.output / "trials.jsonl").open("w") as output:
        for case in cases():
            for seed in SEEDS:
                pair = []
                for mode in ("policy", "fixed_pose"):
                    if time.process_time()-start > 600:
                        raise RuntimeError("600 CPU second budget exceeded; partial JSONL retained")
                    trial = run_trial(args.rl_source.resolve(), upstream, policy_path, seed, case, mode)
                    output.write(json.dumps(trial) + "\n")
                    output.flush()
                    pair.append(trial["metrics"])
                    rows.append(trial["metrics"])
                if pair[0]["initial_sha256"] != pair[1]["initial_sha256"]:
                    raise AssertionError("Unpaired initial conditions")
            print(case["name"], "complete", flush=True)
    with (args.output / "trials.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(status="completed", stage="exploratory_development_no_promotion", trials=len(rows),
                  seeds=list(SEEDS), cases=cases(), evaluator_sha256=foundation.sha256(__file__),
                  foundation_sha256=FOUNDATION_SHA256, policy_sha256=foundation.POLICY_SHA256,
                  elapsed_cpu_s=time.process_time()-start,
                  runtime=dict(python=platform.python_version(), mujoco=mujoco.__version__,
                               onnxruntime=ort.__version__, numpy=np.__version__),
                  protocol=dict(physics_hz=200, policy_hz=50, duration_s=10, push_ticks=[600,619],
                                recovery="1 continuous second: tilt<=5deg, angular speed<=0.5rad/s, xy speed<=0.05m/s",
                                fall="height<0.09m or torso tilt>30deg",
                                initial_clearance="lift by initial floor penetration depth +1mm when needed"),
                  limitations=["Five seeds per case; exploratory only, no new final holdout",
                               "Feet-only collisions and CPU BAM/runtime/sensing limitations inherited",
                               "Initial tilt changes support geometry; recorded clearance avoids floor penetration",
                               "No controller training/tuning or Companion lock change"])
    (args.output / "report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
