"""Opt-in training task; nominal physics and benchmark remain untouched."""
import gymnasium as gym
import mujoco
import numpy as np
from robot_lab.robustness import RobustnessEnv, protocol

TRAIN_SEEDS = tuple(range(4000, 4008))
VALIDATION_SEEDS = (4008, 4009)
CHECKPOINT_STEPS = (5120, 10240, 15360, 20480)


def settling_reward(tilt, speed, action, fallen):
    if fallen:
        return -20.0
    in_band = tilt <= .10 and speed <= .30
    return float(2.0 + 4.0 * np.exp(-(tilt / .10) ** 2)
                 - 4.0 * tilt ** 2 - .5 * speed ** 2
                 - .08 * np.sum(np.square(action)) + 2.0 * in_band)


class SettlingEnv(gym.Env):
    """Deterministic round-robin curriculum over training-only seeds/cases."""
    def __init__(self):
        self.wrapper = RobustnessEnv(protocol()['cases'][0])
        self.action_space = self.wrapper.env.action_space
        self.observation_space = self.wrapper.env.observation_space
        self.total_steps = 0
        self.episode = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        cases = protocol()['cases']
        # First quarter: nominal/small cases; remaining steps include full grid.
        available = [c for c in cases if c.get('strength') != 'medium'] if self.total_steps < 5120 else cases
        self.wrapper.case = available[self.episode % len(available)]
        reset_seed = TRAIN_SEEDS[(self.episode // len(available)) % len(TRAIN_SEEDS)]
        self.episode += 1
        obs = self.wrapper.reset(reset_seed)
        return obs, {'reset_seed': reset_seed, 'perturbation': self.wrapper.case.copy()}

    def step(self, action):
        obs, _, terminated, truncated, info = self.wrapper.step(action)
        self.total_steps += 1
        data = self.wrapper.env.data
        mujoco.mj_forward(self.wrapper.env.model, data)
        tilt = float(np.arccos(np.clip(data.body('torso').xmat[8], -1, 1)))
        speed = float(np.linalg.norm(data.qvel[3:6]))
        reward = settling_reward(tilt, speed, action, terminated)
        return obs, reward, terminated, truncated, dict(info, training_tilt=tilt, training_speed=speed)

    def close(self):
        self.wrapper.close()


def selection_score(summary, original_success_rate):
    p = summary['ppo']
    rate = p['successes'] / p['trials']
    eligible = rate >= original_success_rate - .05 - 1e-12
    # Prefer eligible policies; then recovery, survival, mean duration. Earliest ties.
    return (eligible, p['recoveries'] if eligible else 0, p['successes'], p['mean_seconds'])
