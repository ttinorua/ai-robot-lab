# Inspected sources, licensing and compatibility

This milestone adapts the established additive architecture; no external claim
is reported as Robot Lab performance and no package was installed.

1. Johannink et al., *Residual Reinforcement Learning for Robot Control*, ICRA2019,
   arXiv 1812.03201v2: https://arxiv.org/html/1812.03201v2
   Method III, equation 5 and Algorithm 1 were inspected. A fixed feedback action
   and learned correction are added; the paper's assembly experiments and TD3
   results are not evidence for this robot/PPO combination. Only this architectural
   idea is adapted; article text and external controller weights are not copied.
2. Silver, Allen, Tenenbaum and Kaelbling, *Residual Policy Learning*:
   https://github.com/k-r-allen/residual-policy-learning/tree/ab330ee425463459f1dd7daa4b571104ae449118
   This is a distinct author implementation/paper (arXiv 1812.06298), not Johannink's
   code. Inspected pinned README, requirements, residual_fetch_push_env.py,
   actor_critic_copy_policy.py and rollout_controller.py. The environment adds
   residual to base before stepping, and the actor construction starts at zero
   via matched networks. These inform environment-side composition and zero-mean
   initialization, implemented freshly here. Root repository metadata/full tree
   showed no general top-level code LICENSE; an asset license is not a code grant.
   No author implementation code was copied. Python3.5/Gym0.10.9/numpy1.14.5,
   mujoco-py/mjpro150 and TF/Baselines/HER stack are incompatible with the existing
   Python3.11/Gymnasium/native MuJoCo/SB3 CPU environment without a substantial port.
   Recursive exception retries in legacy rollout generation are not reused.
3. Steven Tang, MIT-licensed SB3 example, inspected at exact commit
   747c5db350694f1e4e59758205948dae6fd403ff:
   https://github.com/steventango/residual-rl/blob/747c5db350694f1e4e59758205948dae6fd403ff/src/residualrl/residualrl.py
   LICENSE, pyproject.toml and README were inspected through the GitHub connector.
   README describes a TD3 PointMaze example. pyproject lists SB3>=2.0/Torch>=1.8
   and optional Gymnasium Robotics. No extras or optional packages were installed.
   Pristine source/pyproject review snapshots and original MIT notice (Copyright
   (c) 2023 Steven Tang) are retained in references/. They are text, not imported.
   The alpha-weighted blend would reduce the full base at default alpha=0.5.
   Its override of predict does not cover installed PPO collect_rollouts, which
   invokes policy(obs_tensor) and then env.step. Therefore it is not used as a
   drop-in PPO policy. New code uses full base torque + bounded residual torque
   in a common pure composition function and a Gymnasium ActionWrapper.

source-review.json records pins and hashes of archived MIT review material.
The Robot Lab implementation is fresh code adapting the published algorithm,
not a modified copy of an unlicensed legacy source. Existing installed SB3 is
used under its own license; no SB3 source is vendored. The pre-training test
collects four inference transitions through actual PPO collect_rollouts without
learn/train, proving the training action path uses the same composition as
explicit evaluation. Untrained model serialization/reload is tested separately.

DeepMind official MuJoCo MPC humanoid standing objectives remain a reference:
https://github.com/google-deepmind/mujoco_mpc/blob/main/mjpc/tasks/humanoid/stand/task.xml
No C++/gRPC build or alternative model is needed or installed for this milestone.
