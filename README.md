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

## How it works
- MuJoCo XML describes a torso, two legs, two motors, ground, and gravity.
- Gymnasium environment produces a 17-dimensional observation: 9 generalized positions and 8 generalized velocities.
- PPO controls the two hip motors with actions between -1 and 1.
- The reward favors remaining upright and penalizes excessive motor action. Episodes stop when the robot falls or after 10 simulated seconds.
- `evaluate.py` tests a trained model on 10 different random initializations.

## Important caveats
This is a starter scaffold, **not a trained robot or a validated walking controller**. Its two fixed legs and hip-only motors are intentionally simple, and stable balancing may require redesigning feet, actuators, observations, reward, and reset distribution. The project has not yet been dependency-installed or run against MuJoCo in this environment. The XML and Python files need runtime validation before claiming training success. A full browser-connected dashboard is a later milestone.

## Next milestones
1. Install dependencies and run a physics smoke test.
2. Verify action/observation shapes and contact stability.
3. Train a baseline policy; record episode length and rewards.
4. Tune the task to reach 10 seconds consistently.
5. Add knees, walking reward, and disturbance testing.
