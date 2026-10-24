# Frozen PPO robustness baseline

PR: https://github.com/ttinorua/ai-robot-lab/pull/1 (base head a247941).

Protocol and implementation were frozen before evaluation; see [PROTOCOL.md](PROTOCOL.md) and frozen-protocol.json. Development seeds 4000–4009 and holdout seeds 5000–5019 were unused in prior reports. No holdout tuning, retraining, model/environment changes, deployment or merge.

## Holdout outcomes

| Case family | PPO survival | Zero survival | PPO / zero mean seconds | Paired gain, 95% CI (s) | PPO / zero recovery |
| --- | ---: | ---: | ---: | --- | ---: |
| nominal | 20/20 | 10/20 | 10.000 / 6.182 | 3.818 [2.247, 5.395] | 0 / 10 |
| pitch | 80/80 | 40/80 | 10.000 / 5.780 | 4.220 [4.204, 4.238] | 0 / 0 |
| linear_velocity | 71/80 | 40/80 | 9.031 / 5.734 | 3.297 [2.831, 3.739] | 0 / 1 |
| angular_velocity | 80/80 | 36/80 | 10.000 / 5.761 | 4.239 [3.431, 5.066] | 0 / 32 |
| push | 80/80 | 35/80 | 10.000 / 5.676 | 4.324 [3.293, 5.304] | 0 / 4 |

Overall PPO survived 331/340 vs 161/340, mean 9.772 vs 5.764 s. Paired gain: 4.008 s [3.488, 4.531]; success-rate difference +0.500 [0.435, 0.565]. There were 170 PPO-only successes and no zero-only successes. All nine PPO falls occurred at initial x velocity −0.50 m/s (11/20 successes in that case).

PPO met the predeclared sustained-upright/low-angular-speed recovery criterion in 0/340 trials; zero action met it in 47/340. No PPO conditional mean recovery time exists. Zero-action recovery/stability windows are passive behavior, not active correction. PPO survival gains with nonzero actions support a benefit of control over no control, but do not establish stable settled recovery. The recovery definition was not relaxed after inspecting results.

## Validation and evidence

Nine perturbation tests passed, including real simulated impulse/momentum response, substep force instrumentation, timing/direction/magnitude, normalization, exact paired reset states/observations, repeatability and leakage, force clearing on exception, sustained recovery and horizon-boundary fall. Two nominal regression tests passed, including unchanged policy 10/10 on seeds 1000–1009. No training smoke tests ran. CI now selects physics, nominal regression and robustness tests explicitly instead of discovering the existing training smoke test.

1020 benchmark episodes used 41.34 process CPU seconds. Selected local tests used 20 policy episodes plus fewer than 25 short/nonpolicy test trajectories; total is below 1100 episodes and conservatively below 60 CPU seconds including failed initial perturbation-test attempts and imports. The persisted ledger covers benchmark evaluations only. No paid services/APIs/GPU or network/credential changes were used.

Raw JSON is archived losslessly as development.json.gz and holdout.json.gz (gunzip -k to inspect; SHA256SUMS includes decompressed hashes). Raw JSON contains reset before/after states and observations, per-step push evidence (including actual partial/zero impulse), per-trial perturbation/seed, flags, recovery-window latency, action effort and paired differences. CSV contains flat per-controller outcomes. Frozen protocol records model/source hashes; reports include dependency versions. SHA256SUMS covers published artifacts.

## Limitations and next decision

This is a 10-second simulation benchmark of one frozen checkpoint on a small robot with broad feet and asymmetric actuators. Only world-x pushes/velocity and y-axis pitch are covered, independently; no lateral, combined, repeated or hardware disturbances. Reset tilts retain nominal root height and may introduce contact transients. Bootstrap intervals are conditional on this fixed scenario grid and 20 holdout seeds, with no multiple-comparison correction. Recovery windows may occur without an initial threshold excursion and can precede later instability; later falls invalidate the recovered outcome. Survival alone is not recovery.

Recommendation: retain this benchmark as the milestone, but continue improving before treating PR #1 as a robust recovery controller. A focused next experiment is to test a controller/reward objective targeting sustained low-angular-speed settling and backward-velocity recovery, using development seeds only. Work must review before any training. The now-inspected holdout must never be reused for tuning or labeled a fresh holdout.

## Reproduction

Decompress the JSON archives first with `gunzip -k experiments/robustness-baseline/*.json.gz`. Use the commands in PROTOCOL.md. Keep published reports intact; the CLI refuses overwrites. All nominal dynamics, reset/fall thresholds, selected policy and viewer remain byte-identical to a247941. Stop after this milestone for independent review.

## Push cost and deployment gate

GitHub repository metadata confirms public visibility. The only automatic PR-branch workflows are Physics validation on standard ubuntu-latest (no container/GPU/larger runner); standard GitHub-hosted runners for public repositories are free. CI performs selected nontraining tests only. Train balance AI push trigger requires main; Pages push trigger also requires main, and neither workflow is manually dispatched. All workflow definitions were inspected before publishing. The user-reported Plus balances were 76% five-hour / 96% weekly with zero credits; these are context, not a new billing measurement. Shell Git transport cannot reach its configured proxy; GitHub connector publication is used without altering network/security configuration. No merge or deployment is authorized.
