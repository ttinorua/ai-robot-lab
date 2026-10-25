# Prepared upstream licensing inquiry — not sent

Proposed destination: a public issue in
https://github.com/LuwuDynamics/xgoduck_hardware

Proposed title: Clarify licenses and provenance for XGO-Duck simulation assets and walking ONNX

## Proposed issue body

We are developing T-Duck, a simulated robotic companion in the public
[AI Robot Lab project](https://github.com/ttinorua/ai-robot-lab/pull/2).
We have run the published XGO-Duck walking policy in CPU MuJoCo/BAM and would like
to preserve the correct licenses and attribution before redistributing assets
or including the robot in a browser viewer.

Could you point us to definitive file-level licenses and upstream provenance for:

1. `LuwuDynamics/xgoduck_rl` revision
   `725ed0c75a73988adc4f9ede280d2d340664e997`:
   `src/mjlab_microduck/robot/xgoduck/robot_walk.xml`, `scene_walk.xml`,
   the referenced `assets/` meshes, and `params/1910_m6.json`.
2. `LuwuDynamics/xgoduck_runtime_arduino` revision
   `8837d5a3bc7cf3746f6da2b55c7b9191026b9838`:
   `python/xgoduck_walk.onnx`, SHA-256
   `57cdebf36e7fa23116270dec96f013a6a64511f37311d322443f5297bdc3d6db`,
   including checkpoint/export provenance and applicable weight license.

We found the RL code's Apache-2.0 license and the hardware repository's
`LICENSING.md`/`UPSTREAM.md` discussion of pending file-level terms. We have not
established whether those code terms cover the exact model assets or weights,
or which inherited Pollen Robotics model terms apply to each file.

Does the applicable grant permit redistributing these exact files and a derived
browser visualization in a public repository? Please identify required notices,
attribution, share-alike/noncommercial conditions, and any separate permissions.

Our intended credit is: “XGO-Duck by Luwu Dynamics, based on Microduck and
microduck_rl by Pollen Robotics; actuator modelling by Rhoban BAM; training
framework mjlab.” Please advise if additional credit is required.

We have kept the model/weight files in external checkouts and have not bundled
them in our repository or viewer pending clarification. Thank you.
