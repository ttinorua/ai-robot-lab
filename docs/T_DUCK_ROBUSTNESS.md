# T-Duck robotics robustness — parallel development

Date: 2026-10-25. Robotics branch: `feature/t-duck-foundation`, PR #2.
Companion branch: `feature/t-duck-companion`, PR #3. No Companion files or protocol
changes are part of this work. Its pinned foundation commit
`629abcd15862822c796cca6a91170fca6ba1d492` remains valid and available.

## What actually ran

`t_duck_robustness.py` reuses the existing verified MuJoCo/ONNX/BAM trial factory
and stepping helper. It checks the unchanged `t_duck_eval.py` SHA-256
`be98b4a9bb7788e19edecf477afb3d2e535e3a94e4901a7dc27defc6f2f51457`.
No controller, model, upstream assets, training, deployment or credentials changed.
The original nominal/holdout evidence is preserved.

The complete development batch contains **180 trials**: 18 scenarios × five seeds
(40000–40004) × policy/fixed-pose control. All trials have a 10-second horizon.
The independent holdout repeats **all eighteen scenarios**, with ten disjoint
seeds (50000–50009) and both controllers, for 360 trials. The same frozen policy,
evaluator, thresholds and scenario list are used; there is no holdout tuning.

Scenarios:

- Standing and forward-command controls.
- Initial roll/pitch offsets of ±10° on top of seeded ±2° nominal perturbations.
- Initial x linear-velocity offsets ±0.25 m/s and pitch angular-velocity offsets
  ±2 rad/s, on top of the seeded nominal velocities.
- External world-x/world-y pushes in both signs, at 0.1 and 0.2 N s. Forces are
  1 or 2 N for exactly twenty 5 ms physics steps, starting at 3 seconds.

Tilting can otherwise place one foot inside the floor. Where needed, both members
of a pair receive the same initial root-height lift equal to penetration depth
plus 1 mm. This is recorded, not hidden tuning; development lift range was
0–9.94 mm. Initial qpos, qvel, latency and SHA-256 are saved for every trial.

Policy runs at 50 Hz and BAM/physics/delay at 200 Hz. Applied forces are cleared
every step, then written to the trunk and integrated from the actual applied
vector. A fall before the full pulse ends is retained as a failure with a partial
impulse, rather than silently treated as a complete disturbance test.

## Metrics and interpretation

Fall thresholds remain root height <0.09 m or tilt >30°, checked using refreshed
post-integration state. A settled interval requires tilt <=5°, angular speed
<=0.5 rad/s, and world horizontal speed <=0.05 m/s continuously for one second.
For push cases, this interval starts no earlier than the pulse end. Recovery
confirmation time includes the confirmation second; it is not onset time.

Successful recovery summaries require **survival AND final settling AND full
disturbance application**. A first recovered interval alone is insufficient.
Forward walking is assessed with displacement, not the standing settling rule.
`peak_tilt_deg` is the maximum sampled after physics integration; the initial
orientation is separately available in the raw JSONL and may have a larger tilt.

Development: policy **90/90 survival**, fixed pose **76/90**. Excluding the forward
case from the standing recovery metric, policy **85/85** and fixed pose **71/85**
meet the complete recovery criterion. The backward pitch offset and backward
linear velocity each gave policy 5/5 survival versus fixed pose 0/5. The stronger
backward push gave 5/5 versus 2/5. These are development results, not proof across
all possible conditions.

Read-only independent review checked all 180 development JSONL records, all CSV
cells, 90 initial-state pairs/hashes, reconstructed tilt/velocity injections,
initial contacts/clearance and applied impulses. No material mismatch was found.

## Fresh holdout results

Completed `reports/t-duck/robustness-holdout-001/`: 360 trials, all eighteen
unchanged scenarios × ten fresh seeds × two controllers. Root audit verifies
all 540 development+holdout CSV/JSONL records and 270 paired initial hashes.
`reports/t-duck/robustness-audit.json` contains per-scenario recomputed summaries.
A separate read-only reviewer independently verified both completed batches, all
CSV fields and paired hashes, impulses, and frozen source/development-report
linkages, with no material discrepancy. Initial tilt values are injected offsets
on top of nominal randomization, not exact absolute torso angles.

| Sampled holdout condition | Policy survival | Fixed-pose survival |
| --- | --- | --- |
| All eighteen cases | 180/180 | 159/180 |
| Negative pitch offset, -10° | 10/10 | 0/10 |
| Negative initial x-velocity offset, -0.25 m/s | 10/10 | 0/10 |
| Negative world-x push, -0.2 N s | 10/10 | 9/10 |
| Each of the other fifteen scenarios | 10/10 | 10/10 |

Across non-forward trials, survival + final settling + complete disturbance
application passed **170/170 policy** versus **149/170 fixed pose**. The failed
fixed-pose negative-pitch trials lasted an average 0.3945 s; negative-velocity
trials averaged 0.376 s. Surviving policy trials all lasted ten seconds. Every
holdout push was applied for its full twenty-step interval, including the
fixed-pose trial that subsequently fell.

Forward-command travel averaged **1.260077 m** for policy versus **0.002775 m**
for fixed pose in ten seconds. Both survived that nominal scenario. The policy
still undershoots the requested 0.2 m/s command.

This establishes an active-control benefit over fixed pose for the specified
negative-pitch/negative-velocity conditions in this simulator. The push-survival
advantage is only one trial out of ten in one case; do not claim broad statistical
push superiority. Most scenarios remain passively survivable at these strengths.

## Reproduce

Use the existing external pinned upstream checkouts, with CPU dependencies from
`requirements-t-duck.txt`; source/asset provenance remains in the upstream manifest.

```bash
python t_duck_robustness.py --rl-source /path/to/xgoduck_rl --runtime-source /path/to/xgoduck_runtime_arduino --output /new/development
python t_duck_robustness_holdout.py --rl-source /path/to/xgoduck_rl --runtime-source /path/to/xgoduck_runtime_arduino --development-report /new/development/report.json --output /new/holdout
python -m unittest discover -s tests -v
```

Existing output directories are never overwritten. JSONL is flushed per trial so
partial evidence survives a failure. Each batch checks a 600 CPU-second budget
between trials; setup and a possible final-trial overrun are outside that check.
Measured development CPU time was 127.536 seconds. No training ran.
Holdout CPU time was 256.223 seconds (383.759 seconds for both batches).
Environment: Python 3.12.14, MuJoCo 3.3.7, ONNX Runtime 1.22.1, NumPy 2.5.4;
versions are recorded in reports. Fourteen local tests pass, including force
integration and both-axis/both-sign coverage checks. No new final-holdout rerun
or parameter selection was performed after these results.

## Limits and next steps

These are sampled simulation conditions with the original feet-only walking
collision model and inherited CPU-BAM, firmware and sensing differences. Full
body impacts, real hardware, uneven terrain and get-up are not validated.
Scenarios share seeds, so scenario totals are not statistically independent
samples; do not infer broad reliability or use a naive pooled confidence interval.
Initial tilt also changes support geometry/clearance, as it physically should.

The Companion continues to use its pinned stable foundation; this benchmark does
not require a Companion update or replace its controller. After independent
holdout/CI review, prioritize a source-compatible fuller collision model and
broader disturbance limits. Keep any model/weight redistribution subject to the
separate file-level licensing review. No external licensing inquiry was sent.
