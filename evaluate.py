import argparse
import numpy as np
from stable_baselines3 import PPO
from robot_lab import BalanceEnv

p = argparse.ArgumentParser()
p.add_argument('--model', default='models/balance_ppo.zip')
p.add_argument('--episodes', type=int, default=10)
p.add_argument('--render', action='store_true')
a = p.parse_args()
env = BalanceEnv(render_mode='human' if a.render else None)
model = PPO.load(a.model)
durations = []
for i in range(a.episodes):
    obs, _ = env.reset(seed=1000+i)
    done = False
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
    durations.append(info['survived_seconds'])
    print(f'Episode {i+1}: {durations[-1]:.2f}s')
print(f'Average: {np.mean(durations):.2f}s | 10-second success: {sum(x >= 10 for x in durations)}/{len(durations)}')
env.close()
