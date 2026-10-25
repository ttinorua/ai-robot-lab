# Fuller collision-model probe

2026-10-25. This is the next bounded robotics investigation after the separate
legacy gravity-test correction in PR #8. It does not change a controller or claim
improved walking, balance, get-up or hardware behavior.

Compared pinned upstream `scene_walk.xml` (feet-only collision) and `scene.xml`
(includes `robot_allcollisions.xml`). Both compile to the same fourteen actuator
joints/order and total mass 0.7977886721912344 kg. The fuller model has fifteen
named collision geoms, versus two feet in the walking model.

Eight deterministic headless drop probes ran: each model started contact free
at root height 0.35 m and roll/pitch ±90°, then advanced 1 second at 200 Hz.
This uses the bare MJCF position servos holding the STAND keyframe (`kv=0`,
with separate joint damping), **not** the PPO/BAM controller. The raw protocol
metadata uses “PD” as shorthand for that damped position-servo setup. Geometry, inertia, gravity and collision masks were not edited.

Results: fuller-body model detected non-foot floor contacts in **4/4** probes;
walking-only model detected them in **0/4**. All states stayed finite. Walking-only
root origins ended below the plane (-0.0249 to -0.0942 m), consistent with the
declared absence of head/trunk/leg collision. Fuller-model roots ended at
0.0468–0.0589 m with head, trunk or leg contacts. These are fixture outcomes,
not universal height guarantees. They confirm why feet-only rollouts cannot
validate full-body falls and recovery.

`results.json` records every contact set, first body-contact time, runtime,
model source hashes and probe hash. No upstream model/mesh/weight is bundled.

```bash
python reports/t-duck/collision-probe-001/probe.py --rl-source /path/to/pinned/xgoduck_rl --output /new/results.json
```

Next: evaluate the unchanged walking policy with a source-compatible fuller
collision factory and paired conditions. Same mass and actuator order are useful
compatibility checks, not evidence that that controller evaluation already passed.
The Companion remains pinned to its proven foundation; this probe requires no
protocol, APK, deployment or baseline replacement. No training or spending occurred.
