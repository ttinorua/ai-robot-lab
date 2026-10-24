# Balance checkpoint experiment — 2026-10-24

The selected policy achieved **10.00 seconds in all 10 evaluation trials**. The controlled final-checkpoint baseline achieved 3.19 seconds on average (2/10 successes). The user-reported historical result of approximately 1.30 seconds could not be independently reproduced: its trained checkpoint was not available locally. Do not present that estimate as a measured baseline.

## Protocol and comparison

Both fresh training runs used the physics, observations, reward, and PPO hyperparameters from base commit `57a8e56bf310b3d41faa1de3e4a3a544d396d932`: training seed 42, CPU, two Torch threads, rollout length 1,024, batch size 128, learning rate 0.0003, entropy coefficient 0.002. A requested 20,000 steps rounds up to 20,480 complete rollout steps. The baseline saved only the final policy; the new run selected a checkpoint using deterministic validation on seeds 2000–2009. Evaluation uses deterministic actions and the existing reset distribution.

| Experiment | Selected training step | Evaluation seeds | Mean seconds | Full-horizon successes |
| --- | ---: | --- | ---: | ---: |
| Zero-action reference, unchanged simulator | — | 1000–1009 | 7.808 | 7/10 |
| Original training, final checkpoint | 20,480 | 1000–1009 | 3.190 | 2/10 |
| Original training, final checkpoint | 20,480 | 2000–2009 | 3.210 | 2/10 |
| Validation-selected PPO checkpoint | 1,024 | 1000–1009 | 10.000 | 10/10 |
| Validation-selected PPO checkpoint | 1,024 | 2000–2009 | 10.000 | 10/10 |
| Additional evaluation after selection | 1,024 | 3000–3009 | 10.000 | 10/10 |

The first ten evaluation seeds were used for baseline comparisons; they are not a never-inspected test set. Checkpoint selection itself uses only seeds 2000–2009. Seeds 3000–3009 were evaluated after the checkpoint was frozen. JSON reports include every individual duration, termination flags, and model hash. `training.json` records all validation checkpoints, actual training steps, dependency versions, and training source hashes. Success requires reaching the time limit **without falling**, including on the final step. No termination thresholds or physics settings were relaxed.

## Findings and changes

The current robot's broad feet already give substantial passive stability, but zero action does not succeed reliably. Continued stochastic PPO training can damage a deterministically successful policy: retaining only the last checkpoint loses the 1,024-step controller. Training now evaluates after actual PPO updates, ranks checkpoints by full-horizon success count then average survival, and retains the earlier checkpoint on ties. The final policy is retained separately for diagnosis.

The existing 17 observations contain nine generalized positions and eight velocities. The model has two limited hip hinges, no knees or ankles, ground friction 1.2, asymmetric foot sizes and motor gears (45/35). These were inspected and retained to isolate the training change. The reward favors upright survival and penalizes effort, angular velocity, and action changes. The action-change term depends on a previous action absent from observations; adding that observation is a reasonable future experiment, but is unnecessary for the verified 10-second target here.

The gravity test previously asserted downward motion while the feet were touching the floor. It now tests free fall clear of contacts. Boundary tests distinguish time-limit completion from falling at the time limit. A regression test evaluates the checked-in policy across the ten evaluation seeds, and an actual PPO training test checks that both checkpoint files reload.

`viewer/index.html` is unchanged, preserving the Android touch controls and replay loader. `viewer/trained-robot.json` is the real 501-frame rollout for seed 1000, exported from `policy.zip`, with the same replay schema, 0.02-second spacing, and model SHA-256. Deployment now uses the reviewed replay in its own commit rather than fetching an unrelated hardcoded historical Actions artifact.

## Reproduce

From the repository root, using the installed environment:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python train.py --steps 20000 --seed 42 --threads 2 --output models/reproduce_balance
.venv/bin/python evaluate.py --model models/reproduce_balance.zip --episodes 10 --first-seed 1000 --json models/reproduce_evaluation.json --require-all-success
.venv/bin/python evaluate.py --model experiments/balance-checkpoint-selection/policy.zip --episodes 10 --first-seed 1000 --require-all-success
.venv/bin/python export_replay.py --model experiments/balance-checkpoint-selection/policy.zip --output /tmp/balance-replay.json
```

For the original baseline, use `train.py` from the base commit with the same environment, seed, threads, and 20,000-step request. The baseline evaluation reports here were generated with the shared evaluation protocol before training was changed. The unchanged simulator and requirements allow direct comparison. Exact dependency versions are recorded in `training.json`; requirements remain ranges, so later package updates may produce different learned policies.

The existing `Train balance AI` workflow supports manual dispatch of 20,000 steps on this branch. It uses CPU PyTorch, runs the tests, trains, requires 10/10 evaluation successes, and uploads the best/final policies, validation history, evaluation JSON, and replay. The 20-minute timeout bounds each run. A failed evaluation fails the job; artifact upload remains best-effort because the repository's existing workflow tolerates artifact quota failures. Local execution is verified; remote Actions execution must be confirmed separately.

## Limits and next experiment

Ten seconds is the existing task horizon, not evidence of indefinite balance, disturbance recovery, walking, or arbitrary starting poses. The reset is upright with hip noise in ±0.05 radians and velocity noise of standard deviation 0.015. These results establish the requested nominal benchmark only. Next, freeze this benchmark and measure separate seeded torso-tilt/velocity disturbances before deciding whether symmetric actuators, additional observations, or reward changes improve robustness. No GUI rendering or Android device test was performed; the viewer implementation is unchanged.
