import argparse
from pathlib import Path
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from robot_lab import BalanceEnv

p = argparse.ArgumentParser()
p.add_argument('--steps', type=int, default=200_000)
p.add_argument('--output', default='models/balance_ppo')
a = p.parse_args()
Path(a.output).parent.mkdir(parents=True, exist_ok=True)
env = Monitor(BalanceEnv())
model = PPO('MlpPolicy', env, verbose=1, tensorboard_log='runs', seed=42, n_steps=1024, batch_size=128, learning_rate=0.0003, ent_coef=0.002)
model.learn(total_timesteps=a.steps)
model.save(a.output)
print(f'Saved model: {a.output}.zip')
env.close()
