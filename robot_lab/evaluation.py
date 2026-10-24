"""Shared evaluation protocol; validation and final evaluation use separate seeds."""
import numpy as np
from robot_lab import BalanceEnv


def evaluate_policy(policy, episodes=10, first_seed=1000, render=False):
    if episodes < 1:
        raise ValueError('episodes must be positive')
    env = BalanceEnv(render_mode='human' if render else None)
    trials = []
    try:
        for seed in range(first_seed, first_seed + episodes):
            obs, _ = env.reset(seed=seed)
            total_reward = 0.0
            for _ in range(500):
                action = np.zeros(2, dtype=np.float32) if policy is None else policy.predict(obs, deterministic=True)[0]
                obs, reward, terminated, truncated, info = env.step(action)
                if not np.isfinite(obs).all() or not np.isfinite(reward):
                    raise RuntimeError(f'Nonfinite simulation at seed {seed}')
                total_reward += reward
                if terminated or truncated:
                    break
            else:
                raise RuntimeError('Environment did not finish within the 500-step horizon')
            trials.append({'seed': seed, 'seconds': info['survived_seconds'],
                           'success': bool(truncated and not terminated),
                           'terminated': bool(terminated), 'truncated': bool(truncated),
                           'reward': float(total_reward)})
    finally:
        env.close()
    return {'episodes': episodes, 'first_seed': first_seed,
            'mean_seconds': float(np.mean([t['seconds'] for t in trials])),
            'successes': sum(t['success'] for t in trials), 'trials': trials}
