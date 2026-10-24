# One bounded settling experiment: negative result

PR #1, branch improve/verified-balance; accepted baseline head 460b57f.
Original benchmark and reports are unchanged. No merge or deployment.

## Development result (17 cases × seeds 4000–4009)

| Controller | Full-horizon survival | Mean seconds | Settled recovery |
| --- | ---: | ---: | ---: |
| Selected candidate (step 5120) | 164/170 | 9.696 | 0/170 |
| Original frozen PPO | 168/170 | 9.898 | 0/170 |
| Zero action | 75/170 | 5.510 | 20/170 |

Candidate-minus-original mean survival: -0.2014 s, 95% paired-seed bootstrap CI
[-0.3520, -0.0514]. Success difference: -2.353 percentage points, CI
[-4.118, -0.588]. Settled-recovery difference: 0, CI [0,0]. Survival loss is
within the predeclared 5-point bound, but positive recovery gain is absent.
Candidate nominal regression: 10/10. Original nominal regression: 10/10.
Development acceptance FAILED. No holdout was run. Seeds 6000–6019 remain unused;
old inspected holdout 5000–5019 remains retired. No second run was attempted.

## Diagnosis and single attempt

Read PROTOCOL.md for choices frozen before training, frozen-choices.json for
source/protocol/dependency hashes, and diagnostics.json plus diagnostic-traces.csv
for raw original/zero traces. On sampled nominal seed 4000 after 2 s, original
PPO has mean pitch 0.80330 rad (~46 degrees), pitch SD 1.13e-8 rad and mean angular
speed 1.05e-7 rad/s. It is stably leaned outside the fixed 0.10-rad recovery band,
not continually oscillating. Other sampled surviving cases exhibit a similar
leaned equilibrium. Candidate nominal late pitch remains 0.80336 rad, SD 6.27e-8,
angular speed 5.69e-7 rad/s. These sampled traces diagnose the observed equilibrium;
they do not prove the reward is the unique cause or characterize every seed.

The opt-in wrapper used training-only reset seeds 4000–4007, a small-to-full
fixed disturbance curriculum, and a stronger upright-band reward. It initialized
from the frozen PPO and ran exactly once with 20480 new steps. Validation used
only seeds 4008/4009, the unchanged 17-case matrix, and four post-update checkpoints.
All four scored 33/34 survival and 0/34 recoveries. Earliest-tie selection retained
step 5120. Selected and final model artifacts are separate. The selected artifact
was reloaded and its timestep checked inside this one actual training run.
No training smoke run or GitHub training dispatch occurred.

Candidate SHA-256:
`bb5cda047e39940ecb3a5e28c31f47bd4a4ac32e2047e87decad9b9b955adab1`.
Frozen original SHA-256 remains
`d00ffe9a13cb9a71e9f596d7b4392bf10edc004b18d6f4c1565fb338021b7244`.

## Validation, budget and cost gate

Four new unit tests cover curriculum/seed isolation, physical reset orientation,
settling reward and fall semantics, post-update checkpoint cadence/selection/ties,
and the development acceptance gate. Checkpoint evaluation is mocked in unit
tests so CI never trains. Nine existing perturbation tests and two original
nominal tests also pass. See validation.txt and training.log.

Training used 5.69 process CPU seconds excluding checkpoint validation (18.12 s).
The complete experiment ledger including development, traces and conservative
20-second test/import/processing allowance is about 72.40 CPU seconds, with 810
explicitly counted evaluation episodes and a conservative 910 including all unit
test/regression trajectories. Measured execution wall was about 7.6 minutes before
publication, versus limits 300 training CPU s / 600 total CPU s / 2500 evaluation
episodes / 15 minutes wall excluding connector publication. Persistent guards,
exclusive one-attempt marker, CPU OS limits and no-overwrite split checks were
used. Frozen checkpoint, environment/XML, original train.py, benchmark code/raw
reports and viewer are byte-identical to 460b57f.

Existing included Cloud CPU only; device=cpu and one thread. No paid service/API,
GPU, purchase, credential/security/network change, merge or deployment. Public
repository and standard ubuntu-latest CI verified. Physics push trigger now only
main; pull_request/manual remain, CPU PyTorch is installed, and selected tests do
not train. Training/Pages push triggers require main; none manually dispatched.

## Evidence and reproduction

Raw per-trial JSON and trace CSV are losslessly gzip archived to keep Git history
small; `gunzip -k experiments/settling-candidate/*.gz` restores them. Flat development
CSV, paired validation reports, reset-state hashes, actual push impulse evidence,
recovery times, actions, flags, candidate/final weights, selection history, loaded
hyperparameters, seed audit and SHA256SUMS are preserved. No reports from the
accepted baseline were overwritten. See PROTOCOL.md and the diagnostic scripts;
run from repository root with PYTHONPATH=. in an independent archived checkout.
Preserve published artifacts before independent reproduction. The CLI refuses a
second training attempt and refuses overwrite of an evaluated split. Regenerating
the frozen manifest is a new experiment and requires another review.

## Recommendation

Do not promote this candidate or describe it as active settled recovery. It
retains the original leaned equilibrium and slightly worsens development survival.
This one attempt does not rule out the objective or curriculum more broadly.
A focused next experiment, only after Work review, is to lower initial Gaussian
action standard deviation to 0.1 while retaining this reward/curriculum and all
other settings. Loaded/selected standard deviations remain about 0.99/1.00 while
deterministic actions are small; reducing exploration could test whether large
stochastic motor excursions prevent learning the upright region. This is a
hypothesis, not a proven explanation. No further experiment runs in this task.
