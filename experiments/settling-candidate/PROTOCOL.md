# Single settling candidate — frozen before training

Prior head 460b57f. Original policy, nominal BalanceEnv/XML, train.py, benchmark
implementation, prior reports and viewer remain byte-for-byte unchanged.

Diagnosis: six cases, original and zero, development seed 4000, raw per-step
traces in diagnostic-traces.csv. Original nominal late pitch averages 0.8033 rad
with standard deviation ~1.1e-8 and mean angular speed ~1.1e-7 rad/s. This is a
sustained leaned equilibrium, not sustained oscillation, in this sample. Other
sampled surviving original trials also settle near 0.803 rad. Traces support
trying a stronger upright objective; they do not prove reward is the only cause.

Exactly one PPO fine-tuning attempt initialized from frozen policy. Seed 71,
CPU one Torch/OpenBLAS/OMP thread, 20480 actual new steps, n_steps 1024, batch
128, n_epochs 10, learning rate 1e-4 constant, entropy coefficient 0. Other loaded
PPO hyperparameters remain unchanged. No learning on any evaluation/holdout reset.
Train reset seeds 4000–4007, deterministic round-robin case/seed scheduler.
First 5120 environment steps use nominal + eight small signed disturbances;
subsequent steps use the unchanged full 17-case grid. Curriculum advances on
resets only; a current episode keeps its starting case. Push physics/schedule
are delegated to the frozen robustness wrapper. Observations remain 17 values.

Opt-in reward replaces only training reward: if fallen, -20; otherwise
2 + 4 exp(-(tilt/0.10)^2) - 4 tilt^2 - 0.5 angular_speed^2
- 0.08 sum(action^2) + 2 I(tilt<=0.10 and angular_speed<=0.30).
Tilt is angle from world vertical and angular_speed is root angular norm.
Rewards use refreshed kinematics. No fall/reset/model thresholds are changed.
The instantaneous bonus approximates settling; selection/evaluation still require
0.5 s continuous membership in the unchanged recovery band and no later fall.

Validation frozen at development seeds 4008 and 4009, all 17 unchanged cases.
Four checkpoints only: after actual PPO updates at 5120,10240,15360,20480 steps.
No pre-update validation. Rank by eligibility (survival rate at least original
validation rate minus 0.05), then eligible recovery count, survival count, mean
survival seconds; retain earliest exact tie. Ineligible policies rank by survival
then duration (recovery does not compensate for the survival constraint).
Record all checkpoints' paired candidate/original evidence; save selected and
final artifacts separately under this new experiment directory, never overwrite
original. Reload selected checkpoint after the one real training run. Unit tests
use mocked checkpoint evaluation, not extra training runs.

Development acceptance: paired candidate/original/zero on seeds 4000–4009 across
all 17 cases; candidate must have strictly more settled recoveries than original,
no more than 5 percentage points survival loss, and 10/10 original nominal seeds
1000–1009. These nominal seeds are a required regression only, not training data.
If failed: stop; no second training run and no new holdout evaluation.

If accepted: freeze candidate hash and all choices; one paired candidate/original/
zero final evaluation on seeds 6000–6019 across the identical 17 cases. Prior
tracked raw reports were checked by parsing seed fields: no 6000–6019 used.
These seeds must be retired after that evaluation. Old holdout 5000–5019 is retired
and neither trained on nor selected on. No post-holdout changes/tuning.

Budgets: at most 20480 new PPO steps; <=300 training CPU s, <=600 milestone CPU s,
<=2500 evaluation episodes, <=900 execution wall s excluding connector publication.
Conservative guards: 270 training CPU s, 290 process CPU s for the training phase
(includes its validation), 550 accumulated CPU s, 2400 evaluation episodes, 850
wall s. Persistent one-attempt marker opened exclusively before training.
Budget includes 12 diagnostic episodes and conservative startup/test overhead.
Evaluation uses frozen trial()/summarize(): paired-seed bootstrap uncertainty,
per-trial reset/push evidence, survival, recovery latency and action effort.
Expected maximum evaluation episodes: 12 diagnostics + 272 validation + 510
development + 10 candidate nominal + 1020 optional holdout + 10 original nominal
regression = 1834, plus bounded unit-test trajectories below 2500.

Use existing installed CPU dependencies only. No paid service/API, GPU, credential,
security/network changes, GitHub training dispatch, merge or deployment. Stop
for Work review after this single experiment, including negative results.

Reproduce independently (one run; use a fresh experiment directory/checkout and
archive prior outputs first; never call reused seeds an uninspected holdout):
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python improve_settling.py train`
then `... improve_settling.py development`; only if development-gate.json accepted
and its candidate hash matches may `... improve_settling.py holdout` run.
The frozen-choices manifest must match source, dependency and protocol hashes.
