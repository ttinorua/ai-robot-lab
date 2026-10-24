# Robot Lab status — 2026-10-24

PR: https://github.com/ttinorua/ai-robot-lab/pull/1
Branch: improve/verified-balance; prior reviewed head a247941.
Checkpoint: experiments/balance-checkpoint-selection/policy.zip, selected at step 1024.
Checkpoint SHA-256: d00ffe9a13cb9a71e9f596d7b4392bf10edc004b18d6f4c1565fb338021b7244

Robustness milestone implemented with a separate wrapper and frozen protocol.
Holdout: PPO 331/340 full-horizon successes vs zero action 161/340; paired survival
+4.008 s (95% seed-bootstrap CI 3.488–4.531). PPO sustained settled recovery 0/340;
zero action 47/340. All nine PPO falls: initial x velocity −0.50 m/s. Nominal
regression remains 10/10. Nine perturbation tests and two nominal tests pass.
No retraining, deployment, merge, paid resources or security/network changes.

See experiments/robustness-baseline/README.md, fixed PROTOCOL.md, source/model
hashes, dependency versions, JSON and CSV. Benchmark budget: 1020 episodes,
41.34 CPU seconds; conservative milestone total below 1100 episodes / 60 CPU s.

Blockers: sustained recovery is unproven; broad feet provide passive stability.
Shell Git proxy is unreachable; use GitHub connector to publish this milestone.
Independent review is pending; no merge or deployment.
Cost gate: public repository, standard ubuntu-latest only, nontraining selected CI;
training/Pages auto triggers require main. Existing PR branch only.

Next task: independent Work review. If approved, design one development-only
experiment for low-angular-speed settling and backward-velocity recovery. Do not
train until that review; allocate a fresh holdout for any future controller.


## Reviewed baseline and single settling attempt

Work accepted baseline 460b57f (PR review 5635858739; prior PR CI 40045624924
succeeded). One approved fine-tuning run completed at 20480 new steps; selected
step 5120, SHA bb5cda047e39940ecb3a5e28c31f47bd4a4ac32e2047e87decad9b9b955adab1.
Traces diagnose sustained ~0.803 rad lean, not persistent oscillation, on sampled
original nominal behavior; candidate retains it. Development candidate/original/
zero survival 164/168/75 of 170; recoveries 0/0/20. Candidate nominal 10/10.
Recovery-gain gate failed; no final holdout and no more training. Seeds 6000–6019
remain unused. See experiments/settling-candidate for frozen choices, raw evidence,
checkpoints and budget (5.69 training CPU s; ~72.40 total CPU s incl reserve;
810 counted evaluations, <=910 conservative total; ~7.6 min execution wall).

Blocker: active settled recovery has not improved; candidate is not promoted.
Next task is Work review of this negative experiment. Proposed next experiment
only if separately approved: lower initial action standard deviation to 0.1 with
this objective/curriculum otherwise fixed. CI is PR/manual plus main-only pushes
and CPU PyTorch. No training dispatch, merge/deployment or paid resources.


## Upright-feedback feasibility milestone

Prior reviewed head 74180dc retained; failed PPO candidate not promoted. No PPO
training in this milestone. Audit confirms original ~0.803-rad lean accompanies
hips at soft -0.8 limits, active limit forces, sustained negative bias and foot-only
support. Neutral gear-aware PD restores upright from reset and the leaned state.
A fixed 32-setting observation-only feedback search selected index 5 (hip K=2,
D=0.48989795; torso K=4, D=0.5; action=torque/[45,35]).

Development survival/recovery: feedback 169/170 and 169/170; PPO 168/170 and 0/170;
zero 75/170 and 20/170. Candidate nominal 10/10. Predeclared engineering gate passed.
One final 6000–6019 evaluation: feedback 336/340 survival AND recovery, PPO 332/340
and 0/340, zero 145/340 and 46/340. All 336 surviving feedback trials finish inside
the band; no clipping or non-foot contacts. Four feedback falls at +0.16-rad initial
pitch retained; no post-holdout adjustment. Seeds 6000–6019 are retired.

See experiments/upright-feedback for joint/contact/COM/reward audit, every gain
trial, fixed protocol, final code/parameter/model hashes, raw paired JSON/CSV,
versions and budget. Three new and eleven preserved local tests pass. Budget at
report generation: 2246 local counted rollouts/resets, 2446 including CI reserve,
~170.57 local process CPU s including allowance; within all caps. No merge,
deployment, security/network/billing change or paid resources. Prior artifacts
and viewer remain byte-identical. CI remains one standard free public Linux PR run.

Upright active recovery is feasible on this grid, not general robotics completion.
Next task: independent Work review. Only after review consider residual control
around this feasible feedback baseline and expanded development disturbances;
no additional development path starts in this task.

Owner steering during publication: prioritize established published solutions.
Preferred next bounded path after Root Work review is Johannink et al. (ICRA2019)
residual control around this frozen successful feedback baseline, not another
blind lower-exploration PPO attempt. Official MuJoCo MPC standing objectives are
a reference; its full C++/gRPC stack/model is not drop-in. Community PD+SAC claims
and licensing remain unverified; nothing installed/copied. Primary references and
reuse rationale: experiments/upright-feedback/REUSE.md. No extra experiment run.
