# Frozen robustness protocol v1

Defined before any development or holdout controller evaluation. No training.
The existing selected step-1024 policy is loaded deterministically on CPU. Its
weights, nominal environment, fall thresholds, reset distribution and viewer
remain unchanged. This isolated wrapper delegates integration to BalanceEnv.

World axes: x forward, y lateral, z up. Each disturbance is tested independently,
with small and medium strengths and both signs, plus a nominal control case:

| Disturbance | Small | Medium | Application |
| --- | --- | --- | --- |
| Initial torso pitch | ±0.08 rad | ±0.16 rad | Unit quaternion about +y at reset; root position unchanged |
| Initial linear velocity | ±0.20 m/s | ±0.50 m/s | Add world-x root velocity to seeded nominal reset |
| Initial angular velocity | ±0.50 rad/s | ±1.00 rad/s | Add root pitch angular velocity about y |
| Torso push | ±0.50 N s | ±1.50 N s | World-x force at torso COM, zero external torque |

Pushes start at t=1.00 s (control step 50), end at t=1.10 s (step 55
exclusive), and use constant ±5 or ±15 N for 0.10 s, spanning ten MuJoCo
0.01 s substeps. Force stays applied during each pair of substeps and is cleared
in a finally block after every control step. Reset also clears force/evidence.
A controller falling before the scheduled push is still a failure and its actual
applied impulse is reported, including zero or partial impulse where applicable.
No resetting/repositioning after a push; no modifications to model parameters.

Paired deterministic PPO and zero-action trials receive exactly equal seeded
initial generalized states and observations. Seeds 4000–4009 are development;
5000–5019 are holdout. Existing reports use 1000/2000/3000 ranges, and none of
these new benchmark ranges have been evaluated before this milestone. Unit tests
use separate 41000-series seeds. Freeze implementation and protocol hashes before
development, verify them before holdout, then evaluate holdout once without tuning.

Full-horizon survival: the unchanged 10 s limit is reached without termination;
a fall on the final step remains failure. Recovery: first continuous 0.50 s window
(25 control intervals) with tilt from vertical ≤0.10 rad and root angular-speed
norm ≤0.30 rad/s, without a fall. Count intervals beginning at/after t=0 for reset
disturbances or t=1.10 s for pushes. Report latency from that origin to the end of
the window. A later fall invalidates the recovered-without-later-fall outcome;
retain first qualifying-window latency for diagnosis. A qualifying window does
not require a preceding threshold excursion: mild perturbations may never leave
the band. Thus this is an operational recovery/stability measure, not proof of
active correction. Zero-action results explicitly measure passive stability.

Record reset states/observations before/after, force schedule with before/after
states, integrated actual impulse, trial seeds, survival/fall flags, recovery,
peak tilt and integrated sum of squared actions (action² s). Compare PPO-minus-zero
survival, success, recovery and action effort. JSON preserves paired trials and
simulator evidence; CSV provides flat controller outcomes. Per-scenario and pooled
95% percentile bootstrap intervals use 4000 paired-seed resamples (RNG seed 61982).
Pooled estimates resample seeds as clusters, retaining all cases in each seed.
Intervals describe these small simulated samples, not hardware performance;
no multiple-comparison correction or causal claim from action effort alone.

17 cases × 30 seeds × 2 controllers = 1020 benchmark episodes. The shared persisted
ledger refuses further episodes at 1450 or 840 process CPU seconds, leaving room
below the milestone limits of 1500 episodes / 900 CPU seconds for selected tests
and overhead. A wall-time guard also stops slow evaluations. Never run training
or training smoke tests. Include only Cloud CPU; no paid APIs, GPU, deployment,
network expansion, credential changes or automatic merge.

Reproduce from repository root (existing .venv):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m unittest discover -s tests -p test_robustness.py -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m unittest discover -s tests -p test_evaluation.py -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python benchmark_robustness.py --split development
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python benchmark_robustness.py --split holdout
```

The CLI refuses to overwrite evaluated reports. For independent reproduction,
use a fresh checkout and move the published JSON/CSV/budget/freeze reports into a
separate archive first; preserve them and do not characterize reused seeds as a
new holdout. Confirm source hashes against frozen-protocol.json before running.
