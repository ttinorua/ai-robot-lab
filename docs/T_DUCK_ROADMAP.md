# T-Duck — AI Robot Lab roadmap

T-Duck is our proposed intelligent robotic companion. AI Robot Lab remains the parent research project. We retain the original two-hip prototype in Git history and migrate only after independently verified simulation tests.

## Source projects (not bundled or endorsed)
- RL and XGO-Duck MuJoCo model: https://github.com/LuwuDynamics/xgoduck_rl
- Runtime and ONNX policies: https://github.com/LuwuDynamics/xgoduck_runtime_arduino
- Hardware: https://github.com/LuwuDynamics/xgoduck_hardware
- Upstream: Pollen Robotics Microduck.

## Milestone TD-01 — reproduce locomotion in simulation
1. Pin exact upstream revisions and record model/policy SHA-256 checksums.
2. Review code, mesh, hardware-design and policy licensing separately. The RL repository uses Apache-2.0; inherited 3D assets may carry different terms. Do not redistribute assets without verification.
3. Validate XGO-Duck MJCF loads and steps in headless MuJoCo with finite positions, sensible contacts and joint ranges. Record robot dimensions, masses, joint ordering, actuator mapping.
4. Inspect ONNX walking/get-up policies for valid inputs, outputs, and preprocessing. Compare with the runtime's observation construction and action scaling. Never assume pretrained ONNX policies are plug-and-play with a generic MuJoCo loop.
5. Run an end-to-end rollout with the original policy and model; measure upright time, falls, forward displacement, and numerical instability across randomized initial conditions. Record video/replay and exact commands.
6. Compare with the current 2-motor baseline. Promote T-Duck to the default viewer only after successful reproducible simulation.

**Acceptance:** 10 consecutive randomized 10-second upright trials with finite physics, plus a documented forward-walking trial. Report failures honestly. Do not claim success from the existence of pretrained files.

## Milestone TD-02 — movement expansion
Turning, fall recovery, terrain variation, command switching and stability under perturbations.

## Milestone TD-03 — intelligent companion
Separate high-level assistant (speech-to-text, dialogue, text-to-speech, vision, planning, network access) from a safety-constrained motion controller. Require explicit permission for external actions; never give an LLM raw actuator authority. Prototype in simulation before physical hardware.

## Constraints
- Reuse existing repository, no paid services, no purchases or production deployment.
- Preserve baseline and prior viewer until replacement passes tests.
- Use a draft PR for integration; no merge without owner approval.
- GPU-intensive mjlab training requires a suitable CUDA machine; do not assume free GitHub runners provide one.

## Current execution evidence

See [T_DUCK_PROGRESS.md](T_DUCK_PROGRESS.md) for the implemented CPU MuJoCo/ONNX/BAM
runner, final development and holdout measurements, exact compatibility limits,
licensing blockers and continuation instructions. Simulation movement acceptance
has measured evidence; full v0.1/viewer integration is not complete.
