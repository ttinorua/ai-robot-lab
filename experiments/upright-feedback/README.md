# Upright feedback: feasibility and final paired evaluation

Parent reviewed head 74180dc; branch improve/verified-balance, PR #1. No PPO training, promotion of the failed PPO candidate, model/physics changes, merge or deployment.

## Main result

An interpretable, observation-only controller establishes upright recovery feasibility on this fixed simulation grid. Engineering development thresholds passed before the final holdout. This is not hardware validation or completion of the robotics mission.

| Split / controller | Survival | Recovery (fixed criterion) | Mean survival s | Final in band |
| --- | ---: | ---: | ---: | ---: |
| Development 4000–4009 / candidate | 169/170 | 169/170 | 9.949 | 169/170 |
| Development 4000–4009 / original | 168/170 | 0/170 | 9.898 | 0/170 |
| Development 4000–4009 / zero | 75/170 | 20/170 | 5.510 | 0/170 |
| Holdout 6000–6019 / candidate | 336/340 | 336/340 | 9.901 | 336/340 |
| Holdout 6000–6019 / original | 332/340 | 0/340 | 9.800 | 0/340 |
| Holdout 6000–6019 / zero | 145/340 | 46/340 | 5.382 | 0/340 |

Candidate nominal regression is 10/10. In development it exceeds 90% survival and 80% recovery with positive recovery gains over both controls. Holdout candidate recovery gain is +98.824 percentage points over PPO (95% paired-seed bootstrap CI +97.647 to +99.706), and +85.294 points over zero (+83.529 to +87.059). Paired mean survival gains: +0.1008 s vs PPO (CI -0.0482 to +0.2487), +4.5193 s vs zero (+4.1119 to +4.9192). Thus superiority in recovery is clear on this grid; survival superiority over PPO is not established by that interval.

Holdout candidate mean episode tilt 0.00943 rad; PPO 0.75133 rad, zero 0.51520 rad. Mean integrated squared action is 0.0001024 action² s for candidate vs 0.0168465 for PPO. Saturation fraction and non-foot floor-contact fraction are zero for all three in this comparison. All surviving feedback trials end inside the unchanged band, distinguishing upright control from an early qualifying window followed by lean. Zero has 46 early recovery windows but zero final-band outcomes, consistent with the frozen operational metric. No metric was changed.

Four holdout feedback falls are pitch_medium_+1 at seeds 6001,6006,6014,6017. Original PPO falls are medium backward velocity. Candidate had one development fall: medium backward velocity at 4001. These failures are retained, not tuned away. Seeds 6000–6019 were checked unused, evaluated once after code/parameter freeze, and are now retired. Old 5000–5019 were not used for training/selection.

## Joint-limit hypothesis: supported by causal audit

On nominal seed 4000, original PPO settles at torso pitch +0.803303 rad, hip angles -0.803400/-0.802802 rad, against the XML -0.8 soft limits. Active limit constraint forces are 2.924/2.387 Nm (soft penetration 0.00340/0.00280 rad), with sustained motor torques -1.887/-0.318 Nm and actions about -0.0419/-0.00909: not actuator saturation. Legs remain approximately vertical because torso pitch plus hip angle is near zero. Only the two feet contact the floor; there is no torso/leg ground prop. The eight positive normal forces sum to 35.316 N, matching 3.6 kg × 9.81. COM projection is inside the actual contact support polygon. Root height is 0.60755 m, versus 0.67477 m with neutral PD.

Gear-aware neutral hip PD (8 Nm/rad, damping 1 Nm s/rad) from reset settles near -0.000656 rad pitch, hips near zero, no active limit constraints. Switching only controller from PPO to this PD at 2 s restores that upright state without falling on both audited seeds (4000/4001). This intervention, simultaneous limit loading and planted feet support the mechanically supported joint-limit lean explanation. They do not isolate every contact/gravity/actuator contribution as a unique cause. No joint limit, contact rule or physics parameter was altered.

Zero action and constant ±0.02 Nm biases do not reliably hold upright across the audited seeds. Tiny matched +0.02 Nm per hip reduces torso y angular velocity relative to zero torque in both planted and lifted diagnostics; the negative torque reverses that response. Thus the positive torso-pitch feedback sign is empirically checked with unilateral ground contact and without it. Numerical LQR/inverse dynamics was unnecessary once low-order feedback empirically demonstrated feasibility; no unsupported linear contact model was assumed.

Foot geometry and gearing are asymmetric: left half-foot size [0.16,0.09,0.035] m and motor gear 45; right [0.13,0.065,0.035] and gear 35. Each desired physical joint torque is divided by its own gear, rather than assuming equal actions give equal torque.

## Reward, observation and termination audit

The original nominal reward already prefers upright: measured steady components sum to ~4.642 for PPO lean and ~5.99955 for neutral PD. Exact components and all sampled contact names/positions/forces, limit forces, COM, support polygon and hip/root states are in the audit archives. Maximum recomputation error in reward components is 1.6e-11. This evidence does not show reward is the unique cause of the learned equilibrium.

Observations are nine qpos plus eight qvel; quaternion is wxyz. Normalized observed quaternion pitch agrees with native torso orientation within 3.4e-8 rad in the original audit. MuJoCo leaves derived kinematics at an intermediate substep; frozen termination uses that value, while recovery refreshes final kinematics. Maximum nominal-audit Rzz lag is ~0.00281 during transients and negligible at equilibrium, insufficient to explain the 0.803-rad lean. Frozen height>0.43 and Rzz>0.55 allow tilt up to ~0.9884 rad, so the lean is legitimate nominal survival but not upright recovery. No thresholds were relaxed.

## Fixed search and selected controller

All 32 settings and failures were logged: four audit controls plus 28 predetermined hip/torso feedback combinations, with no fine stage or extra gain tuning. Tuning used only seeds 4000/4003 and seven predefined cases. Four shortlisted settings were checked on 4008/4009 over the full matrix; index 5 was selected before full development. Some high gains saturated and failed; these negative settings remain in search.json.gz and search.log.

Selected parameters: hip_k=2 Nm/rad, hip_d=0.4898979486 Nm s/rad, shared torso pitch_k=4 Nm/rad, pitch_d=0.5 Nm s/rad. Per hip torque is -hip_k*q_i - hip_d*dq_i + 0.5*(pitch_k*pitch + pitch_d*omega_y), divided by [45,35] and clipped to [-1,1]. Only current observed state is used; no clock, seed, scenario, future impulse or simulator access. Time-specific switching appears only in the audit, never the candidate. selected.json and final-freeze.json preserve hashes.

## Tests, budgets and costs

Three new tests cover torque signs/gearing/clipping/finite input discipline, selection/gate isolation, exact nominal agreement with frozen evaluation, upright PD and nominal reward components. Nine existing perturbation tests and two nominal regression tests pass. No training smoke test, PPO learn call, dependency installation, GPU or paid service was used locally. CI remains PR/manual plus main-only push, CPU PyTorch, standard free public-repo ubuntu-latest; new tests are added without training or duplicate PR-branch push validation.

The persisted ledger counts 2246 local rollouts/resets including all tuning failures and test resets, with another 200 reserved as a conservative CI test-rollout bound (2446 total bound <3000). Local measured process CPU plus conservative allowance is 170.57 s (<600); execution wall at this checkpoint is 846.5 s (<1200, connector publication excluded). Guards are below user limits. User-provided account context: 96% five-hour / 89% weekly allowance, zero credits, auto-reload OFF and app-credit usage OFF; no billing changes or purchases.

## Evidence, reproduction and limits

Raw JSON (including full trial pairing, reset/push evidence, sampled complete contacts, action/posture metrics and traces) is losslessly gzip archived. Plain development/holdout CSVs permit independent recomputation; SHA256SUMS includes raw/decompressed hashes. Decompress archives with gunzip -k before inspecting/reproducing in an independent archived checkout. The frozen source keys retain the original absolute checkout path /workspace/ai-robot-lab; reproduce with an independent archived checkout mounted at that same path so the guard matches without changing frozen code. Fixed definitions and commands are in PROTOCOL.md; all scripts live here. No phase is overwritten or holdout repeated.

All prior nominal/frozen/failed PPO artifacts, raw reports, robustness source/protocol, original env/XML/train.py and viewer are byte-identical to 74180dc. Feedback is a new opt-in alternative; no original checkpoint or replay is overwritten.

Limitations: short horizon, modest fixed independent sagittal perturbations, broad feet, asymmetric simplified robot, small seed sample and four holdout failures. COM-in-support is only static evidence, not a general stability proof. Existing recovery windows can precede later lean; final posture is reported separately. No lateral/combined/repeated disturbances, walking or hardware claims. Review this feasible feedback baseline before any future path; a focused next development path could be residual control around it with expanded development disturbances and a fresh holdout, but no such training or further experiment starts here. Stop for independent Work review.

## Established solutions and next path

See [REUSE.md](REUSE.md) for Johannink et al. residual RL, the official MuJoCo MPC standing reference, licensing/reuse distinctions and owner steering. Prefer adapting published base-feedback-plus-residual control around this frozen feasible baseline after Root Work review. No additional experiment or controller change was made.
