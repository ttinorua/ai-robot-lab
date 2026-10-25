"""Headless upstream collision coverage probe, not a movement-policy evaluation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

import mujoco
import numpy as np

REVISION = "725ed0c75a73988adc4f9ede280d2d340664e997"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rl-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite evidence")
    root = args.rl_source.resolve()
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        parser.error("Unexpected upstream revision")
    subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=True)
    directory = root / "src/mjlab_microduck/robot/xgoduck"
    results, models = [], {}
    for scene in ("scene_walk.xml", "scene.xml"):
        model = mujoco.MjModel.from_xml_path(str(directory / scene))
        model.opt.timestep = .005
        models[scene] = dict(mass_kg=float(sum(model.body_mass)),
                             actuator_joints=[model.joint(int(j)).name for j in model.actuator_trnid[:,0]],
                             named_collision_geoms=[model.geom(i).name for i in range(model.ngeom)
                                                    if "collision" in model.geom(i).name])
        for axis in (0, 1):
            for sign in (-1, 1):
                data = mujoco.MjData(model)
                mujoco.mj_resetDataKeyframe(model, data, model.key("STAND").id)
                data.qpos[2] = .35
                data.qpos[3:7] = [math.cos(math.pi/4), 0., 0., 0.]
                data.qpos[4+axis] = sign*math.sin(math.pi/4)
                data.qvel[:] = 0.
                mujoco.mj_forward(model, data)
                if data.ncon:
                    raise AssertionError("Drop must start contact free")
                floor, seen, first_body = model.geom("floor").id, set(), None
                for _ in range(200):
                    mujoco.mj_step(model, data)
                    mujoco.mj_forward(model, data)
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                        raise AssertionError("Non-finite drop")
                    for contact in data.contact:
                        if floor in (contact.geom1, contact.geom2) and contact.dist <= 0.:
                            other = int(contact.geom1 if contact.geom2 == floor else contact.geom2)
                            name = model.geom(other).name
                            seen.add(name)
                            if "foot_collision" not in name and first_body is None:
                                first_body = float(data.time)
                results.append(dict(scene=scene, tilt_axis=("roll", "pitch")[axis],
                                    tilt_deg=sign*90, initial_contacts=0,
                                    floor_contact_geoms=sorted(seen), first_nonfoot_contact_s=first_body,
                                    final_root_z_m=float(data.qpos[2]), duration_s=float(data.time), finite=True))
    if models["scene.xml"]["actuator_joints"] != models["scene_walk.xml"]["actuator_joints"]:
        raise AssertionError("Actuator order differs")
    if abs(models["scene.xml"]["mass_kg"]-models["scene_walk.xml"]["mass_kg"]) > 1e-12:
        raise AssertionError("Mass differs")
    for trial in results:
        if (trial["first_nonfoot_contact_s"] is not None) != (trial["scene"] == "scene.xml"):
            raise AssertionError("Collision coverage did not match the declared models")
    report = dict(upstream_revision=revision, runtime=dict(python=platform.python_version(),
                  mujoco=mujoco.__version__, numpy=np.__version__),
                  source_sha256={p:hashlib.sha256((directory/p).read_bytes()).hexdigest()
                                 for p in ("scene_walk.xml", "scene.xml", "robot_walk.xml", "robot_allcollisions.xml")},
                  probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  models=models, trials=results,
                  protocol="Four deterministic 1s drops per model, root0.35m,roll/pitch±90deg,200Hz; bare MJCF PD holds STAND",
                  limitations=["No PPO/BAM policy execution, get-up, balance or hardware claim",
                               "Upstream geometry/masks unchanged; no asset redistribution",
                               "Compatibility of mass/order alone does not establish walking-policy performance"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(dict(trials=len(results), fuller_body_contacts=4, walking_body_contacts=0)))


if __name__ == "__main__":
    main()
