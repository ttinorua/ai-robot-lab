# Established solutions and next-milestone reuse

Owner steering received during publication, after this controller and holdout
were frozen. This note changes documentation only. No further experiment,
training, controller adjustment, dependency installation or deployment occurred.
Work supplied the following primary-source review; this milestone does not claim
a new independent reproduction of those external projects.

## Published residual-control architecture — preferred next path

Johannink et al., *Residual Reinforcement Learning for Robot Control*, ICRA 2019:
- Paper: https://arxiv.org/abs/1812.03201
- Author project: https://residualrl.github.io/

Reuse the published architecture: an existing feedback controller provides the
base action and a learned residual adds a correction. The paper demonstrates
robot assembly; it is not evidence that a particular residual algorithm, gain or
pretrained policy will solve this two-hip biped. Our frozen feedback baseline
provides task-specific feasibility evidence that the assembly demonstration does
not. Do not describe the architecture as a new Robot Lab invention.

After Root Work review, the next bounded implementation should adapt this
architecture around the successful, frozen gear-aware feedback controller.
Predeclare residual units/allocation (joint torque then division by 45/35),
limits, zero-residual baseline, seeds, learning/evaluation budgets and acceptance
criteria before training. Verify that zero residual reproduces the existing
controller. Keep the current code/parameters as an immutable comparison. Do not
copy external weights or gains; use the local observations and measured physics.
The current milestone does not select an RL algorithm, launch residual training
or authorize an unbounded search. Both 5000–5019 and 6000–6019 are retired holdouts;
any future final evaluation needs a fresh, verified disjoint range.

## Official MuJoCo MPC — reference objectives, not a drop-in dependency

Google DeepMind official source:
https://github.com/google-deepmind/mujoco_mpc

Existing humanoid standing task:
https://github.com/google-deepmind/mujoco_mpc/blob/main/mjpc/tasks/humanoid/stand/task.xml

Work's primary-source check identifies Apache-2.0 licensing and standing
objectives involving height/balance, COM velocity, joint velocity and control.
These are useful established design references. The full C++/gRPC build and its
different humanoid model are not a drop-in replacement for this Python two-hip
robot. Reuse appropriate objective ideas only after inspecting their definitions
and maintaining attribution/license obligations for any actual copied source.
Do not assume its gains, model, pretrained artifacts or performance transfer.

If residual control does not address the remaining hard tilt case, consider a
separately budgeted comparison with a model-predictive controller after Work
review. It must retain unilateral-contact constraints and the same local model
and evaluation definitions. No MPC build, installation, model redesign or MPC
experiment occurred here.

## Community example — unverified, not installed

https://github.com/ryanrahman27/Residual-RL illustrates a claimed PD+SAC humanoid
push-recovery approach. Its claims and source licensing must be verified before
any code reuse. It is not a primary proof of success for our biped, is not treated
as proven, and has not been installed or copied in this milestone.

## Reuse versus local implementation

The current small feedback family was needed to measure torque signs, correctly
allocate asymmetric gears and test upright feasibility with this actual model.
It does not replace established residual-control/MPC research. The result now
supports adapting a published base-feedback-plus-residual architecture rather
than repeating ungrounded reward-only PPO variants or recreating a full robotics
stack. Finish this frozen evidence milestone and stop for independent Root Work
review before implementing that next bounded path. Routine development authority
already exists; this review is technical review, not a new owner-permission gate.
