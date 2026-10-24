# One frozen residual-feedback experiment

Parent reviewed head 20ee9e3; CI40069199261 verified successful and independent
review read before starting. No other agent/training/evaluation process active.
All original physics/env/XML/train.py, source benchmarks, reports, checkpoints,
frozen feedback controller/parameters and viewer remain unchanged.

Source-first architecture and compatibility assessment: SOURCES.md. Action:
base torque = frozen Feedback.predict(obs) * [45,35]; residual = 0.10 Nm * clip(z,-1,1)
per hip; total torque = clip(base torque + residual, -[45,35], [45,35]); action =
total torque/[45,35]. Base coefficient is exactly one, never alpha=0.5. Only the
existing 17 state observations are used. No direct base forces, clock, seed,
future impulse, scenario or privileged observations enter either policy.
Training ActionWrapper and explicit evaluation share compose().

Torque bound selected before training from development-only audited feedback:
sampled per-hip 95th percentiles ~0.117/0.092 Nm, 99th ~0.505/0.495, maxima
~0.810/0.849 Nm. 0.10 Nm is below transient p99/max and <0.3% of weaker actuator
capacity35 Nm; these sampled maxima are not global safety bounds. Initial Gaussian
std0.05 normalized =0.005 Nm. Bound/derivation in torque-bound-evidence.json.
Record raw residual clipping, post-SB3 wrapper clipping, total torque clipping,
residual effort and sampled base/residual/total composition. PPO itself clips raw
sampled z to [-1,1] before env.step, so callback separately counts pre-wrapper
clipping. Evaluation composes the raw deterministic mean with the same clipping.
Zero residual must exactly reproduce full feedback trajectories.

Exactly ONE actual PPO learn attempt; exclusively created attempt marker, no retry.
Fresh residual MLP64x64 actor/critic; action output layer weight/bias zeros; log std
log(0.05). PPO seed83, CPU one Torch/OMP/OpenBLAS thread. 32768 actual steps,
rollout1024, batch128, epochs10, constant LR1e-4, gamma0.99, GAE0.95, clip0.2,
entropy0, default vf_coef0.5/max_grad_norm0.5. No external pretrained weights.
Initialization/reload and four inference-only collect_rollouts transitions are
tested before learn; those are not extra training attempts.

Training: all 17 unchanged cases, deterministic round-robin by episode. Reset
seed cycles4000–4007 independently of case index. Never 4008/4009, old/future
holdouts or nominal regression seeds. Actual used reset seeds/counts are logged.
Reward replaces only training reward: fallen -20; otherwise
1 + 2 exp(-(tilt/0.10)^2) -2 tilt² -0.1 angular_speed² -0.05 sum(clip(z,-1,1)²)
-0.01 sum(total_action²) + I(tilt<=0.10 and angular_speed<=0.30).
Tilt and speed come from current observation, no future data. Physics, falls,
benchmark horizon and original rewards/code remain unchanged. Refresh kinematics
post-step to match the frozen instrumented evaluator.

Four post-update validation checkpoints only:8192,16384,24576,32768. Fixed seeds
4008/4009; fixed cases nominal, pitch_medium_+1, linear_velocity_medium_-1,
push_medium_-1/+1 (10 trials/checkpoint,40 total). Reference base validation uses
matching rows of the immutable upright-feedback development archive, with archive
hash and paired initial-state hash checks. Rank survival-eligible (at least base
survivals) first, then recoveries, survival count, mean survival; earliest tie.
Store every checkpoint, selected and final separately, with hashes and raw trials.
No holdout data used for ranking, reward/torque choices or training.

Full development: residual/base/originalPPO/zero paired identical resets on4000–4009
and all17 unchanged cases (680 episodes). Candidate nominal regression1000–1009
(10 episodes), required acceptance check only. Gate: nominal10/10, strictly more
settled recoveries than BASE and no survival-count loss versus BASE. Same frozen
0.10 rad /0.30 rad/s /0.5s continuous recovery criterion with no later fall, 10s
horizon and fall-at-horizon failure; report final posture/nonfoot contacts/effort.
If no positive gain, retain feedback, stop, no extra train or new holdout.

Only if gate passes: freeze candidate/model/source/choice hashes and evaluate
ONCE on verified-unused7000–7019, four controllers ×17cases ×20seeds=1360 episodes.
Reserve/retire before that run even if interrupted. No post-holdout adjustment.
5000–5019 and6000–6019 remain retired and are not training/selection inputs.

NEW milestone caps:32768 actual training steps,300 training CPU s,600 total CPU s,
2500 evaluation episodes,1200 execution wall s excluding connector publication.
Guards at270 training CPU s,290 total training-phase process CPU s (validation
included),550 accumulated CPU s,1140 wall s,2250 local evaluation episodes with
250 reserved for the single public CI tests. Main worst-case evaluations2090
(40validation+680development+10nominal+1360optional holdout); tests/resets counted
including pre-training tests. Conservative25 CPU s startup/test/processing reserve.
Only existing included Cloud CPU and installed packages; no paid APIs/GPU/services,
training dispatch, network/security/billing changes, merge or deployment.

Reproduce in independent archived checkout at /workspace/ai-robot-lab (frozen
source keys retain this mount) with PYTHONPATH=., OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1 and existing .venv: run.py train, then run.py development; only
if saved gate is accepted and hashes unchanged may run.py holdout be invoked.
Published outputs must be archived first; neither a training marker nor evaluated
phase is overwritten. Reused seeds are never an uninspected holdout. Stop for
independent Work review after this one experiment, including a negative result.
