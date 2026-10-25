"""Record gravity/contact ablations and the physics suite for any source checkout.

Run with the desired Python/MuJoCo environment; this never changes source files.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

import gymnasium
import mujoco
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite evidence")
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from robot_lab import BalanceEnv
    trials = []
    for name, gravity, lift, zero_velocity in (
        ("nominal_contact", -9.81, 0., False),
        ("nominal_contact_zero_gravity", 0., 0., False),
        ("free_fall", -9.81, 1., True),
        ("free_fall_half_gravity", -4.905, 1., True),
        ("free_fall_zero_gravity", 0., 1., True),
    ):
        env = BalanceEnv()
        env.reset(seed=42)
        env.model.opt.gravity[2] = gravity
        env.data.qpos[2] += lift
        if zero_velocity:
            env.data.qvel[:] = 0.
        env.data.ctrl[:] = 0.
        mujoco.mj_forward(env.model, env.data)
        initial = dict(z=float(env.data.qpos[2]), vz=float(env.data.qvel[2]),
                       az=float(env.data.qacc[2]), contacts=env.data.ncon,
                       minimum_contact_distance_m=min((float(c.dist) for c in env.data.contact), default=None),
                       constraint_z=float(env.data.qfrc_constraint[2]))
        max_actuator_force = float(np.max(np.abs(env.data.qfrc_actuator)))
        for _ in range(10):
            mujoco.mj_step(env.model, env.data)
            max_actuator_force = max(max_actuator_force, float(np.max(np.abs(env.data.qfrc_actuator))))
        trials.append(dict(case=name, gravity_z=gravity, initial=initial,
                           final=dict(z=float(env.data.qpos[2]), vz=float(env.data.qvel[2]),
                                      time_s=float(env.data.time)),
                           max_abs_actuator_force=max_actuator_force))
        env.close()
    suite = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                            "-p", "test_physics.py", "-v"], cwd=repo, capture_output=True, text=True)
    spec = importlib.util.spec_from_file_location("audited_physics_test", repo / "tests/test_physics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    negative_controls = {}
    for gravity in (0., 9.81):
        test = module.TestPhysics("test_gravity")
        test.setUp()
        test.env.model.opt.gravity[2] = gravity
        try:
            test.test_gravity()
            negative_controls[str(gravity)] = "accepted"
        except AssertionError:
            negative_controls[str(gravity)] = "rejected"
        finally:
            test.tearDown()
    paths = ("tests/test_physics.py", "robot_lab/env.py", "assets/robot.xml")
    report = dict(runtime=dict(python=platform.python_version(), mujoco=mujoco.__version__,
                               numpy=np.__version__, gymnasium=gymnasium.__version__),
                  source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
                  source_sha256={p: hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths},
                  dependency_scope="Exact CI Python and physics dependencies; unused SB3/Torch/CUDA/TensorBoard omitted",
                  trials=trials, physics_suite=dict(exit_code=suite.returncode, output=suite.stdout+suite.stderr),
                  default_gravity_negative_controls=negative_controls)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(dict(output=str(args.output), runtime=report["runtime"],
                          suite_exit_code=suite.returncode)))


if __name__ == "__main__":
    main()
