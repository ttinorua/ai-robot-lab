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
