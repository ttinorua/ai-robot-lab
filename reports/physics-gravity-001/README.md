# Physics validation failure — reproduced and corrected

Date: 2026-10-25. Failed run:
https://github.com/ttinorua/ai-robot-lab/actions/runs/40187307819

## Exact failure and root cause

The run belongs to Companion PR #7, branch
`feature/tduck-companion-secure-reconnect`, head
`7ca0d27d7f4abcf30806d628b7b16f526d3acc8a`. Actions actually checked out its
merge ref `002b8497f19baf18f565f0983ebc9fd643dee3bf`, against Companion base
`1072cff2347bf8fde0cb732354479129dd5d131c`. That base is the Companion branch,
not main. The isolated fix is based on main `57a8e56`; it includes no Android or
Companion changes and can be integrated by its owner through the approved process.

The original five-test suite was reproduced from the exact merge ref using
**CPython 3.11.17, MuJoCo 3.17.0, NumPy 2.4.6 and Gymnasium 1.4.0**. It produced
the identical assertion: `0.6760083499334241` is not less than `0.675`; the other
four tests passed. The physics dependencies match the failing CI installation.
Unused SB3/PyTorch/CUDA/TensorBoard packages were omitted locally: these tests
import only Gymnasium, NumPy, MuJoCo and `robot_lab`. No training was run.

The nominal reset is a contact/settling configuration, not free fall. Seed 42
randomizes joint angles and generalized velocities. At the test's initial state:

- Root height: 0.675 m; vertical velocity: -0.0292655278 m/s.
- Four floor contacts; minimum contact distance: **-0.0058555468 m**.
- Upward generalized constraint force: 61.49098797; root vertical acceleration:
  **+7.02962503 m/s²**, although gravity is -9.81 m/s².
- Maximum actuator generalized force is **zero** throughout the diagnostic.

The solver resolves penetrating foot contacts, which can raise the root while
gravity remains correct. Net height change during contact cannot isolate gravity.
With gravity disabled in a diagnostic-only ablation, the same nominal contact
state rises even farther, to 0.6834703647 m. This is not a production change.

With the robot raised 1 m, all velocities/controls zero and no contacts, the
measured values after 0.1 s are:

| Gravity | Initial z | Final z | Final vertical velocity |
| --- | --- | --- | --- |
| -9.81 m/s² | 1.675 m | 1.621045 m | -0.981 m/s |
| -4.905 m/s² | 1.675 m | 1.6480225 m | -0.4905 m/s |
| 0 | 1.675 m | 1.675 m | 0 |

These match constant-acceleration semi-implicit Euler integration. There is no
evidence here of a gravity integration defect or actuator-driven lift. The same
original failure and free-fall results reproduce on MuJoCo 3.3.7 with the same
Python/NumPy/Gymnasium versions, so this is not a new MuJoCo-version regression.
This diagnosis does not claim general validation of every contact-solver behavior.

## Smallest executable correction

Only `tests/test_physics.py` changes executable project behavior, and only inside
tests. The default-gravity test now:

1. Keeps the real robot model, raises it above the floor and zeros velocities and
   controls inside a disposable test environment.
2. Verifies no contacts initially and at every step.
3. Steps MuJoCo directly over the same 0.1 s interval.
4. Checks the full linear velocity vector against `g*T`, absolute tolerance 1e-9.
5. Checks vertical displacement against continuous free fall, allowing the
   mathematically derived semi-implicit Euler position error, not an arbitrary
   widened tolerance.

For N steps, dt timestep and T=N*dt:

`v_N = g*T`; `z_N = z_0 + 0.5*g*T² + 0.5*g*dt*T`.

Hence the position tolerance is `0.5*abs(g_z)*dt*T + 1e-9`. The tight independent
velocity assertion catches missing or incorrectly scaled gravity. The default
test still requires downward gravity. A new regression test repeats the isolated
fixture with zero and half-strength fields, excluding leftover contact/controller
kicks and verifying acceleration scales with the configured field. No test is
disabled or skipped. Zero/reversed default fields are also rejected by the fixed
default-gravity test in the recorded diagnostic negative controls.

No changes to `robot_lab/env.py`, `assets/robot.xml`, reset posture, actuators,
rewards, policies, pretrained files, viewer, training scripts, dependencies or
Companion code. Changing nominal initialization solely to satisfy the old assertion
would have disturbed the existing baseline and was unnecessary.

## Version matrix and preserved evidence

| Source/tests | MuJoCo 3.17.0 | MuJoCo 3.3.7 |
| --- | --- | --- |
| Failing Companion merge ref, original test | 4 pass, 1 fail | 4 pass, 1 fail |
| Current robotics PR #2, commit 61eb241 | 5 physics tests pass | 5 physics tests pass |
| Isolated fix, existing four + gravity + field-strength regression | 6 pass | 6 pass |

Robotics PR #2 already contains an earlier contact-free fixture. It was tested
independently rather than assumed broken or changed. Its environment/model Git
blobs match the failing branch exactly (`efbb6d7…`, `aa3bbf3…`). The isolated port
adds explicit zero-control setup, a tighter analytically justified displacement
bound and field-strength regression. A read-only reviewer independently reproduced
the old failure and confirmed all six fixed tests on both engine versions and the
error-bound derivation. Existing robotics/movement evidence is preserved.

Each JSON report records runtime versions, exact source-file SHA-256 values,
diagnostic states and complete unittest output. Reports collected before publication
record the source checkout's base commit; the file hashes identify the actual
tested working-copy test bytes. `fixed-*.json` were collected on Companion base
1072cff with this test-only patch; the same patch was also applied and all six
tests passed on the isolated main-based branch before publication.

Files: `failed-merge-mj317.json`, `failed-merge-mj337.json`, `fixed-mj317.json`,
`fixed-mj337.json`, `robotics-baseline-mj317.json`, `robotics-baseline-mj337.json`.

To reproduce in the desired pinned physics environment, use:

```bash
python reports/physics-gravity-001/reproduce.py --repo /path/to/source-checkout --output /new/report.json
python -m unittest discover -s tests -p test_physics.py -v
```

The diagnostic refuses to overwrite reports and records expected original-test
failure without suppressing it. CPython 3.11.17 and both selected MuJoCo versions
were installed into separate local CPU environments; original simulator runtimes
were left intact. The repository's existing standard Ubuntu CI validates the fix;
no new workflow, workflow dispatch, training job or unattended automation is added.

## Impact, handover and remaining work

This is a **validation correction**, not a movement improvement: production robot
motion is unchanged. The measurable improvement is a reproducible gravity gate
with six passing tests instead of a false failure. Main and Companion branches
must not be merged or updated automatically. The Companion worker owns applying
the exact test-fix commit through the approved integration process.

Robotics continues separately: balance and walking evidence remains in PR #2,
including the 180/180 paired robustness holdout survival result. The next bounded
simulation task is validating upstream's fuller collision model without replacing
the proven controller. No spending, credential/security change, production
deployment or model replacement is part of this fix.
