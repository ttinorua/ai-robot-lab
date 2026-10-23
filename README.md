# AI Robot Lab v0.1

A Microduck-inspired **original** minimal biped robot for reinforcement-learning experiments. Not affiliated with Microduck or its makers.

## Goal
Train a PPO policy to keep a two-hip biped upright for 10 simulated seconds. The controller receives positions and velocities and commands two hip motors.

## Run locally (Python 3.11 recommended)
```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python train.py --steps 100000
python evaluate.py --episodes 10
python evaluate.py --episodes 3 --render
```

Use `tensorboard --logdir runs` to inspect training metrics. Longer runs may be required. GUI rendering needs a machine with graphics/display support. On Colab, train headlessly; download the saved model for local visualization.

Training retains the best deterministic validation checkpoint (seeds 2000–2009)
as `models/balance_ppo.zip` and the final policy as `models/balance_ppo.last.zip`.
More training can reduce stability, so evaluate the selected checkpoint. For a
bounded experiment, use `python train.py --steps 20000`; the default uses two CPU
threads. To save per-trial results and enforce the ten-trial goal:

```bash
python evaluate.py --episodes 10 --first-seed 1000 --json evaluation.json --require-all-success
```

The [verified checkpoint experiment](experiments/balance-checkpoint-selection/README.md)
achieved 10.00 seconds in all ten evaluation trials, compared with a measured
3.19-second final-checkpoint baseline. Its policy, individual results, validation
history, and best replay are included. This verifies nominal balance under the
existing reset distribution; it does not establish disturbance recovery.

## How it works
- MuJoCo XML describes a torso, two legs, two motors, ground, and gravity.
- Gymnasium environment produces a 17-dimensional observation: 9 generalized positions and 8 generalized velocities.
- PPO controls the two hip motors with actions between -1 and 1.
- The reward favors remaining upright and penalizes excessive motor action. Episodes stop when the robot falls or after 10 simulated seconds.
- `evaluate.py` tests a trained model on 10 different random initializations.

## Important caveats
This is a minimal balance experiment, **not a validated walking controller**. Its two fixed legs and hip-only motors are intentionally simple. The checked-in policy has been trained and evaluated headlessly with MuJoCo, but harder reset distributions, disturbances, and walking remain unvalidated. A full browser-connected dashboard is a later milestone.

## Next milestones
1. Measure recovery from seeded torso tilts and velocity disturbances.
2. Compare symmetric actuators and additional observations on that harder benchmark.
3. Add knees and a walking objective after balance robustness is established.
