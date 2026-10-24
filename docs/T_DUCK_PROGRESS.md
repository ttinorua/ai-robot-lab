# T-Duck development handover

Updated 2026-10-25. Project: AI Robot Lab. Robot: T-Duck.
Branch: `feature/t-duck-foundation`; draft PR: https://github.com/ttinorua/ai-robot-lab/pull/2.

## Latest parallel robotics milestone

Continued robotics testing independently of Companion PR #3. New benchmark code
and evidence are documented in [T_DUCK_ROBUSTNESS.md](T_DUCK_ROBUSTNESS.md).
Development (180 trials) and a fresh holdout (360 trials) ran without controller
changes or training. Holdout survival was 180/180 for policy versus 159/180 for
fixed pose; settled non-forward recovery was 170/170 versus 149/170. An injected
negative pitch offset of 10° and a negative initial x-velocity offset of 0.25 m/s
each gave 10/10 policy survival versus 0/10 fixed pose. The stronger negative
x push of 0.2 N s gave 10/10 versus 9/10. These are sampled-condition results; feet-only
collisions and inherited sensing/runtime limits remain.

`t_duck_eval.py` remains byte-for-byte unchanged at the verified SHA-256. Companion
PR #3 and its foundation lock to `629abcd` remain unchanged. No protocol or APK
change is needed for these separate robotics experiments. Existing nominal models,
holdouts, checkpoints, viewer and source history are preserved. Robotics and
Companion development do not need to wait for each other; available included
usage and explicit independent review still bound each task.

Next robotics priority: source-compatible fuller collisions and sensing/delay
fidelity before harder falls/get-up or promoting hardware claims. Companion's
online hosting and phone connection remain its separate TC-03 scope. No
continuous unattended task launching is claimed by this update.

## Current milestone

**CPU simulation movement acceptance passed for the explicitly described model.**
This is not full v0.1 completion: browser integration and asset redistribution remain
blocked by unresolved file-level rights. Hardware, getting up, rough terrain, and
broad disturbance recovery are unverified. Do not merge or deploy automatically.

Implemented `t_duck_eval.py`: the actual upstream XGO-Duck walking MJCF/meshes,
published walking ONNX, upstream inference observation helper, and vendored BAM's
existing CPU MuJoCo actuator controller. No training, invented replacement robot,
GPU, hardware drivers, or paid services. Assets remain in external checkouts and
are **not** included in this repository.

## Measured evidence

Final development: `reports/t-duck/development-003/`, seeds 10000–10009.
Final holdout: `reports/t-duck/holdout-002/`, previously unused seeds 30000–30009.
Holdout ran only after development passed; no subsequent controller tuning.
Each case/controller combination has ten independent resets. Policy and fixed-pose
baseline use identical initial qpos/qvel and latency, recorded and SHA-256 paired.
Fixed pose means constant home targets through the same BAM dynamics, not disabled motors.

| Final holdout, 10 seconds each | Policy | Fixed-pose baseline |
| --- | --- | --- |
| Standing, upright trials | 10/10 | 10/10 |
| Forward command 0.2 m/s, upright trials | 10/10 | 10/10 |
| Forward travel, mean | 1.253574 m | 0.001831 m |
| Forward travel, range | 1.165055–1.362257 m | -0.002205–0.006230 m |
| Falls across standing + forward | 0/20 | 0/20 |

All twenty policy holdout trials lasted the full 10 seconds. Forward walking is
supported by distance **and** alternating left-only/right-only foot contact logs,
not just survival or drifting. Standing alone does not outperform passive stability.
The achieved forward speed (~0.125 m/s) is below the requested 0.2 m/s; precise
velocity tracking is not solved.

Development also measured left and right turns at forward 0.1 m/s and yaw ±0.5 rad/s:
10/10 upright each; mean unwrapped yaw +3.8276/-3.5758 rad over 10 seconds.
These are exploratory development results, not separate holdout claims.
A +x torso push of 0.5 N for exactly twenty 5 ms physics steps at 3 seconds
delivered **0.05 N s**, verified from applied force × timestep. Both policy and
fixed pose survived 10/10; this small push does not demonstrate superior recovery.

`report.json` records thresholds, exact initial states, policy metadata, dependency
versions, evaluator SHA-256, and source revisions. `trials.csv` contains every trial;
`trace.csv` samples motion at 5 Hz and includes final/failure states. Per-trial
survival, minimum upright/height, foot contacts, applied impulse and latency are
measured at 200 Hz. Full physics states are not logged at every timestep.
Final development/holdout consumed 75.71/31.89 CPU seconds respectively.

`development-001` is an archived diagnostic run, not the accepted evidence:
its floating-time push window delivered 0.0475 N s instead of 0.05 N s, and lacked
the final evaluator hash. The integer-step force schedule fixed this; the entire
development batch was rerun as 002 before holdout. Do not silently replace old evidence.

The earlier `development-002` and `holdout-001` are retained as archived evidence
from the pre-audit evaluator, not the final every-physics-step acceptance evidence.
Their orientation/site/contact caches could lag integration by one timestep.
`audit-001.json` records the earlier data-consistency audit; `audit.json` records
the corrected final batches. No policy, action mapping, threshold or reward was
tuned in response to a holdout.

## Exact integration and limits

- RL source: `LuwuDynamics/xgoduck_rl` at `725ed0c75a73988adc4f9ede280d2d340664e997`.
- Runtime policy source: `LuwuDynamics/xgoduck_runtime_arduino` at `8837d5a3bc7cf3746f6da2b55c7b9191026b9838`.
- Hardware licensing/provenance reviewed at `b5e9ff16a98f7bbe5c146aad29ad38f0dde30a89`.
- ONNX: `python/xgoduck_walk.onnx`, SHA-256
  `57cdebf36e7fa23116270dec96f013a6a64511f37311d322443f5297bdc3d6db`.
- MJCF: `src/mjlab_microduck/robot/xgoduck/scene_walk.xml`.
- 61 observations: body angular velocity (3), projected gravity (3), home-relative
  joint positions (14), joint velocities (14), previous raw actions (14), twist
  command (3), head command (4), body command (6). Upright gravity is `[0,0,-1]`.
- 14 radian action offsets in **validated metadata joint order**, scale 1.0.
  Mouth servo is not a policy action. ONNX normalization is already embedded.
- ONNX home metadata is used consistently for initial joints, observations and
  action targets; its angles are rounded to 0.001 rad. The generic helper's
  hardcoded MicroDuck home and default XML are not used.
- Root height 0.139439 m is the pinned XGO walking configuration, not the generic
  helper's 0.125 m or scene STAND's 0.139158 m. Random roll/pitch ±2°, each joint
  ±0.01 rad, initial generalized velocities N(0,0.015); these are modest perturbations.
- MuJoCo 3.3.7, ONNX Runtime 1.22.1 CPU provider, one inference thread. Policy 50 Hz,
  physics 200 Hz. Motor targets delayed 3–6 **physics** steps (15–30 ms), seeded.
- HLS1910 `1910_m6.json`, STS3215 actuator, firmware gain 5, voltage 7.7 V,
  group battery sag gain 0.1, floor 7.0 V. One grouped BAM controller sums all motors.
  Actuators are converted from companion position PD to torque mode before BAM.
- Acceptance: all ten standing AND all ten forward trials survive ten seconds,
  root height >=0.09 m, trunk upright cosine >=cos(30°), every forward trial
  travels >=0.20 m. Upright/height checked every physics step; NaN/Inf aborts.
- **Fidelity limit:** CPU BAM `MujocoController` is an existing upstream method,
  but is not the trained mjlab actuator implementation. It does not reproduce
  mjlab's full gain/friction/sensing randomization and constraint settings.
  This harness uses instantaneous ground-truth observations, not sensor filtering
  or the training joint-velocity observation lag.
- **Runtime limit:** actual runtime uses firmware KP6/KD20 and action smoothing;
  those are not reproduced here. This evaluates a training-style simulation,
  not exact deployed firmware behavior or sim-to-real readiness.
- **Collision limit:** original Walk MJCF enables feet-only floor collisions.
  Height/orientation fall criteria prevent upside-down survival passing, but body
  impacts, self collisions, obstacles and get-up cannot be validated with this model.

The companion-PD diagnostic stayed upright but barely moved. Reusing the existing
CPU BAM path produced walking; no mass, geometry, inertia, gravity, friction or
reward tuning was used to obtain acceptance.

## Reproduction

Use separate, unmodified checkouts at the pinned commits. Do not commit downloaded
meshes, MJCF, runtime source or policy binaries until their terms are established.

```bash
python -m pip install -r requirements-t-duck.txt
python t_duck_eval.py --rl-source /path/to/xgoduck_rl --runtime-source /path/to/xgoduck_runtime_arduino --output /new/development
python t_duck_eval.py --rl-source /path/to/xgoduck_rl --runtime-source /path/to/xgoduck_runtime_arduino --output /new/holdout --stage holdout --development-report /new/development/report.json
python -m unittest discover -s tests -v
```

The runner checks source revisions and tracked modifications, policy SHA-256,
tensor dimensions, joint order, command layout, scale, and finite home values.
It refuses to overwrite evidence or run holdout after an evaluator change.
Each batch has a 600 CPU-second stop. No network calls or training occur in the
runner. File hashes are in `docs/t-duck-upstream-manifest.json`.

## Licensing and attribution

Credit: **XGO-Duck by Luwu Dynamics, based on Microduck and microduck_rl by
Pollen Robotics; actuator modelling by Rhoban BAM; training framework mjlab.**
No endorsement is claimed. Original rights and notices must remain intact.

| Component | Verified status | Current treatment |
| --- | --- | --- |
| RL code and vendored BAM | Apache-2.0 LICENSE files and source notices present | Import from pinned external checkout; preserve licenses/notices when vendoring later |
| Runtime code | No root LICENSE at pinned revision | No runtime code copied |
| Exact ONNX weights | No explicit weight redistribution grant established | Local evaluation only; no weights bundled |
| XGO meshes and MJCF geometry/inertia | File-level upstream provenance and grants unresolved | No model assets bundled or published in viewer |
| Hardware designs | `LICENSING.md` says final scope/terms pending; `UPSTREAM.md` calls for file-level audit | No hardware/design files copied |

Sources: the pinned repositories' README/LICENSE, hardware
[`LICENSING.md`](https://github.com/LuwuDynamics/xgoduck_hardware/blob/b5e9ff16a98f7bbe5c146aad29ad38f0dde30a89/LICENSING.md)
and [`UPSTREAM.md`](https://github.com/LuwuDynamics/xgoduck_hardware/blob/b5e9ff16a98f7bbe5c146aad29ad38f0dde30a89/UPSTREAM.md).
The code license alone does not establish rights to every inherited model/weight.
Next rights task: trace the exact files/revisions and explicit grants; seek owner-
authorized maintainer clarification if the public record cannot resolve it. No
email or other person-directed outreach has been sent.

## Review, preservation and continuation

Work independently inspected PR #2, failed physics CI, upstream source and actual
ONNX metadata, then implemented and executed this harness. Codex independently
completed a read-only source/fidelity/license review in
https://chatgpt.com/local/01a16e64-d3a8-7062-bb9d-cf0e461830fa.
Its findings (home mismatch, physics-vs-policy delay, firmware gain difference,
CPU-vs-mjlab limitations and rights gaps) are incorporated above. The initial harness audit independently recomputed the 140 rows and 70 paired
initial-state hashes, but found a medium-severity stale-derived-state defect after
`mj_step`. The correction calls `mj_forward` immediately after every physics
integration and adds a real MuJoCo regression crossing the 30° boundary in one
step, including site-position consistency. Development was rerun and a fresh
holdout uses seeds 30000–30009; the earlier 20000 range is retired. Final independent read-only review of corrected commit
`03e9acbd7922c8db37989fba86195bc06833e214` accepted the narrow simulated movement
milestone, found no material remaining defect within its bounded scope, and
independently verified all 140 CSV/JSON rows, 70 paired initial hashes and both
report evaluator hashes. Physics CI
https://github.com/ttinorua/ai-robot-lab/actions/runs/40105913649
passed all twelve tests; readiness CI 40105913660 also passed. CI tests do not
rerun the externally sourced motion batches.

The earlier PR #1 residual experiment was preserved at
`bfa9a29552042ca9a157701c9c0c4c0012ce281c`; its interrupted 8192-step attempt
showed no gain and stopped. PR #1 is not merged. Original robot XML, checkpoints,
viewer and recoverable history remain untouched by this branch's implementation.

The old `test_gravity` failure was a contact fixture error: starting on the floor
does not require decreasing root height. It now uses contact-free, zero-velocity
free fall and verifies both g*t velocity and approximate gravitational displacement.
Local physics/readiness/acceptance-gate tests pass (12 tests). Independently
recomputed all 140 final CSV rows and all 70 paired initial-state hashes;
repeated development seed 10000 for standing/forward with exact trial-record matches
(`reports/t-duck/audit.json`). Standard public
Ubuntu CI installs only CPU evaluation and Gymnasium dependencies (no unnecessary
SB3/PyTorch/CUDA download for these tests). Standard public Ubuntu CI is used; no training or viewer deployment is triggered on this branch.

Existing hourly monitor `6adbf32585c081918df167f4e4a1c0e2` was updated for T-Duck;
no duplicate schedule was created. It may review meaningful GitHub changes and
conditionally delegate one bounded task only after verifying no active task,
included allowances and zero-spend guards. **Future scheduled browser access and
task launching remain unverified. Continuous unattended engineering is not claimed.**

Next priorities: resolve asset rights;
then validate fuller collision/sensing/runtime parity before integrating a verified
T-Duck replay/model into the existing viewer on this development branch. No merge,
production publication, hardware purchase, paid training or security change is authorized.

## Management ledger and owner decision

- One new Codex review thread, three bounded read-only handoffs: source review,
  initial code/evidence audit, correction review. Zero duplicate T-Duck coding tasks.
- Two evaluator issues were corrected and archived: the initial push window and
  stale post-integration derived state. The review defect was fixed before
  promoting the strict gate; no failed training or new training occurred.
- Shared included-usage snapshots during this session: 5-hour allowance 93%→52%
  remaining; weekly 77%→70%. These are account-wide observations, not isolated
  per-task metering. Credits stayed zero; auto-reload and app-credit use remained off.
- No merge, production deployment, hardware purchase, credentials/security change
  or additional spending. Existing robot work/viewer remains preserved.
- Owner authorization is needed before contacting upstream maintainers.
  [Prepared licensing inquiry](T_DUCK_LICENSE_INQUIRY.md) contains the exact proposed
  public destination, title and message. It has **not** been sent. Resolving the
  missing grants is necessary before model/weight redistribution in the viewer.
- The existing hourly monitor is configured for T-Duck, with no duplicate schedule.
  Scheduled browser task launching remains unverified; no continuous unattended
  development claim is made.
