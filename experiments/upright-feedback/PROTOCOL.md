# Upright feedback feasibility and finite development search

No PPO training. Prior reviewed head 74180dc. All original/failed policies,
nominal env/XML/train.py, robustness implementation/protocol/reports and viewer
remain byte-identical. New scripts/controllers/evidence are opt-in in this folder.

Audit before gain search: original PPO and four declared diagnostic policies
(zero, hip PD 8 Nm/rad + 1 Nm s/rad, constant ±0.02 Nm per hip), nominal seeds
4000/4001; six matched tiny torque trials (±0.02 or zero Nm per hip, planted and
lifted 1 m); two interventions switching PPO to the same neutral PD at 2 s from
its leaned state. All 18 rollouts count. Time-specific switching is a causal audit
only; the feedback candidate has no time/scenario/disturbance input. The audit
confirms ~-0.803 hip angles, active soft lower-limit forces, sustained negative
motor torque and foot-only support for the +0.803-rad lean. Neutral PD restores
upright from reset and the leaned state. Positive hip torque reduces torso y
angular velocity in matched local tests. This warrants a positive pitch-feedback
sign. No joint limits/contacts/physics are changed. Contact frames/normal forces,
hip limit constraint forces, COM/support bounds and nominal reward components are
recorded. Soft-limit penetration is expected; a limit is not an exact hard stop.

Controller receives only the existing 17 observed qpos/qvel values, stateless:
normalize wxyz root quaternion, pitch=atan2(R_xz,R_zz), omega_y=observed qvel[4].
Free-joint angular velocity is body-local; y coincides with pitch axis for pure
pitch. General large roll/yaw is outside this controller design. Hip q/dq are
observed entries [7:9]/[15:17]. Physical joint torque for each hip:
  -hip_k*q_i - hip_d*dq_i + 0.5*(pitch_k*pitch + pitch_d*omega_y) + bias_Nm.
Actions = clip(torque / [45,35], -1,1), respecting actual asymmetric gearing.
No hidden simulator fields, clock, seed, reward, future disturbance or schedule.

Exactly 32 distinct declared parameter sets, fixed before search:
indices 0–3 are the audit zero/PD/±bias policies. Remaining 28 are Cartesian
hip_k=[2,8,32,128], hip_d=2 sqrt(0.03*hip_k), with
(pitch_k,pitch_d)=[(0,0),(4,0.5),(16,1),(64,2),(0,2),(16,4),(64,8)].
Full numeric grid and hashes: frozen-search.json. This is a deterministic coarse
grid, no adaptive fine stage, random search or further manual gain settings.

Tune only on seeds 4000 and 4003 (within 4000–4007) and seven fixed cases:
nominal, pitch_medium_-1/+1, linear_velocity_medium_-1,
angular_velocity_medium_+1, push_medium_-1/+1. 32*7*2=448 rollouts.
Log all settings/trials/falls, including zero/bias failures. Rank by recoveries
without later fall, survivals, lower non-foot floor-contact fraction, mean
survival, then lower integrated action². Stable earliest index breaks ties.
Take only the four highest tuning settings to selection on 4008/4009, all 17
cases (136 rollouts). Choose highest same ranking; ties retain shortlist order.
No selection from full development comparison or holdout. No additional gains.

Final development: selected feedback/original PPO/zero on all 17 unchanged cases
and seeds 4000–4009 (510 rollouts), exact paired reset states/observations. Candidate
nominal regression uses 1000–1009 (10 rollouts), solely as required regression.
Success/recovery horizon/definitions unchanged: reach 10 s without falling,
including last step; tilt <=0.10 rad AND angular norm <=0.30 rad/s for 25 continuous
0.02-s intervals after reset or push removal, no later fall. These operational
windows can occur before later lean; also report final posture/band membership,
mean/peak tilt, action effort/saturation and non-foot contact fraction. Never
mislabel an early qualifying window or ground-braced posture as sustained upright.
New instrumentation matches frozen trial() nominal outcomes in a regression test.

Engineering screen: candidate nominal 10/10, >=90% full-grid development survival,
>=80% recovery and strictly positive paired recovery gain over BOTH original and
zero. These are screening thresholds, not completion of robotics/hardware mission.
If passed, freeze selected parameters/code hashes (already fixed by selection),
then one final paired evaluation on unused seeds 6000–6019 (1020 rollouts). Verify
prior CSV/JSON seed fields first; no earlier milestone evaluated this range. Retire
at start even if final evaluation is interrupted. No holdout tuning or retries.
If failed, never evaluate holdout or start another development path in this task.

Budgets: whole milestone <=3000 controller rollouts, <=600 process CPU seconds,
<=1200 execution wall seconds excluding connector publication. Persistent budget
counts audits/search/selection/comparisons and test rollouts, failures included.
Reserve conservative 20 CPU seconds for imports/tests/processing. Guards at 2800
rollouts / 550 CPU s / 1140 wall s, OS CPU limits per phase, bounded 500-step trials.
At most 2142 main rollouts (18+448+136+510+10+1020) plus counted tests. No uncontrolled
loops, dependency installation, paid resources/APIs/GPU, network/security changes,
GitHub training dispatch, merge or deployment. Only included existing Cloud CPU.

Reproduce from repository root using existing .venv and PYTHONPATH=., OMP_NUM_THREADS=1,
OPENBLAS_NUM_THREADS=1: run audit.py, run.py search, run.py development; run.py holdout
ONLY if the saved development gate passes with unchanged hashes. Published phases
are not overwritten. Archive outputs first for independent reproduction; reused
seeds are never an uninspected holdout. Run selected tests only; never training
smoke tests. Source hashes are verified before each search/evaluation phase.
