# Source-reused residual wrapper: interrupted single attempt, no measured gain

PR #1 / improve/verified-balance; parent 20ee9e3, reviewed feedback retained.
CI40069199261 was verified successful before starting; no other active task.

## Outcome and integrity limitation

Exactly one PPO learn attempt began, bounded to32768 steps. It stopped after
8192 actual new steps, at the first post-update validation checkpoint. A new paired
base-state-hash metadata string was mistaken for a trial by the CSV exporter,
raising AttributeError. This is a reporting implementation error, not a physics
or residual-control failure. The checkpoint/model and validation JSON had already
been saved. No training was resumed or repeated. In-memory per-episode training seed/clipping aggregates were not flushed before the exception; they are unavailable, not reconstructed or claimed zero. The allowed deterministic seed schedule and clipping code are preserved; development per-trial clipping measurements are available. Checkpoints16384/24576/32768 and
a final model do not exist; the four-checkpoint protocol was not completed.

The exact pre-fix source and original frozen manifest are preserved. The fix skips
metadata in CSV export, adds a focused regression test and attests the reporting
source hash change. Controller/reward/bound/seed/model choices remain frozen.
No original frozen manifest was rewritten to hide the change. Existing attempt
marker, source guard and interrupted-status holdout guard forbid a retry/holdout.
The selected checkpoint is the sole saved checkpoint, not a completed ranking of
four checkpoints. Its model was reloaded and num_timesteps8192 verified. The new
runner regenerates only the partial validation CSV, then evaluates development.

| Development controller | Survival | Settled recovery | Mean survival s |
| --- | ---: | ---: | ---: |
| Partial residual checkpoint | 169/170 | 169/170 | 9.948706 |
| Frozen feedback | 169/170 | 169/170 | 9.948706 |
| Original PPO | 168/170 | 0/170 | 9.897647 |
| Zero action | 75/170 | 20/170 | 5.510235 |

Residual-minus-feedback survival and recovery differences are zero; paired-seed
bootstrap intervals are [0,0]. Both fall on medium backward velocity seed4001.
Candidate nominal1000–1009:10/10; original nominal regression also10/10. Candidate
final-in-band169/170, no non-foot contact, total clipping or deterministic residual
clipping. Mean episode tilt0.008206 versus feedback0.007989 rad; mean action²
integral0.000096893 versus0.000096778. These observations show no benefit for this
partial checkpoint, not that residual RL or the full intended protocol cannot help.
Gate FAILED for lack of positive recovery gain; feedback is retained. No new
holdout ran;7000–7019 remain unused.5000/6000 ranges remain retired.

## Source-first reuse and actual action path

SOURCES.md records direct paper/method inspection, author code pin and compatibility,
modern SB3 example pin747c5db350694f1e4e59758205948dae6fd403ff, original MIT copyright/
license, and exact archived review sources. No legacy/third-party package or
weights were installed/imported. We freshly adapt the published additive method
using a Gymnasium ActionWrapper and one compose() shared by training/evaluation.
The full base is never halved. Inspecting installed PPO showed collect_rollouts
calls policy(obs), so a predict-only mixin is not used.

Per hip: base physical torque + clip(z,-1,1)*0.10 Nm, then clip to45/35 Nm actuator
capacity and divide by45/35. Bound was derived BEFORE training from audited
feedback development effort/torque, not holdout data; see torque-bound-evidence.json.
Actor mean initialized exactly zero; normalized Gaussian std0.05 =0.005 Nm.
No free-base force, future event/scenario/time input or privileged state is used.
Only existing17 state values enter residual/base policies. All train resets are
4000–4007, validation4008/4009, no holdout training/selection. Fixed choices and
expected32768-step protocol remain in PROTOCOL.md; the interruption is not hidden.

Model ZIPs here contain RESIDUAL policies only. Use ResidualController or the
ActionWrapper to compose with the frozen base; do not treat them as standalone
motor-action policies in original evaluate.py. Original behavior remains intact.

## Tests and budget

Five pre-training tests pass: exact zero-residual trajectories, full-base physical
composition/sign/gearing/clipping/finite inputs, seed isolation, untrained model
save/reload, actual PPO collect_rollouts action routing and no-loss/gain gate.
The four collected test transitions perform no optimizer update or learn call;
they are not extra training runs. A reporting regression test now passes; two
original nominal tests pass. Initial/final pre-training test runs and counts are
preserved (56 reset episodes); the two nominal tests add10 policy episodes.

The timed training/checkpoint region CPU upper bound is5.31 s, including its10-trial
checkpoint validation (imports are covered by the25-second overhead reserve; no isolated training timing was fabricated). New milestone
ledger: 766 local evaluations/resets, 1016 including250 reserved
for CI; 101.18 process CPU seconds including conservative25-second overhead reserve;
1097.6 execution wall seconds before connector publication. All below caps.
The attempt stopped on export error, not budget exhaustion. No spending, GPU,
new packages, billing/security/network change, merge/deployment or training dispatch.
Public standard ubuntu-latest PR-only CI remains CPU/nontraining; inference-only
test collection is explicitly distinct from PPO training.

## Evidence, reproduction and next review

Raw per-trial JSON/CSV, paired state/impulse evidence, base/residual/total torque
samples, clipping, source/model hashes, dependency versions, selection reconstruction,
original traceback, initial/checkpoint models and exact reporting fix are preserved.
Large raw JSON is losslessly gzip archived; gunzip -k before inspection. Frozen
source keys retain /workspace/ai-robot-lab; independent archived reproduction must
use that mount. Cached base validation also requires restoring the immutable upright-feedback/development.json.gz archive with gunzip -k before independent reproduction. The existing attempt marker forbids a second training invocation.
All original physics/code, benchmarks/reports, checkpoints, feedback and viewer
are byte-identical to20ee9e3.

Recommendation: keep the reviewed feedback baseline. Before any further learning,
Work should review the corrected exporter and shared composition/provenance tests.
A future separately bounded run could test the SAME predeclared residual design
with a working full checkpoint pipeline; this partial attempt does not justify
changing architecture/gains or claiming literature performance locally. No further
run or development path starts in this task; stop for Work technical review.

## Owner priority supersedes further two-motor work

During archival publication, owner moved project priority to T-Duck/XGO-Duck
migration on PR#2 feature/t-duck-foundation. This PR#1 experiment is archived as
an interrupted, no-gain partial result with a corrected exporter. Earlier technical
recommendations are historical, not active plans for another two-motor attempt.
No further training, holdout or original two-motor improvement is authorized in
this task. Preserve checkpoint/history, finish reporting and stop. Work will
launch a separate bounded T-Duck task afterwards; this task does not start it
or modify PR#2.
