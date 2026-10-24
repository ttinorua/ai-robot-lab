"""Train PPO and retain the strongest deterministic validation checkpoint."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from robot_lab import BalanceEnv
from robot_lab.evaluation import evaluate_policy


class BalanceCheckpoint(BaseCallback):
    """Evaluate after PPO updates, never on the final evaluation seeds."""
    def __init__(self, output, episodes=10, first_seed=2000, frequency=5000):
        super().__init__()
        self.output = output
        self.episodes = episodes
        self.first_seed = first_seed
        self.frequency = frequency
        self.next_evaluation = 0
        self.best_score = (-1, -1.0)
        self.selected_steps = None
        self.history = []

    def _on_step(self):
        return True

    def _evaluate(self):
        result = evaluate_policy(self.model, self.episodes, self.first_seed)
        score = (result['successes'], result['mean_seconds'])
        # Keep the earlier checkpoint on ties; more training can reduce stability.
        if score > self.best_score:
            self.best_score = score
            self.selected_steps = self.num_timesteps
            self.model.save(str(self.output) + '.zip')
        result['timesteps'] = self.num_timesteps
        self.history.append(result)
        print(f"Validation at {self.num_timesteps}: {score[0]}/{self.episodes}, "
              f"{score[1]:.2f}s; selected step {self.selected_steps}", flush=True)
        self.next_evaluation = self.num_timesteps + self.frequency

    def _on_rollout_start(self):
        # The previous rollout has now been used for an actual PPO update.
        if self.num_timesteps > 0 and self.num_timesteps >= self.next_evaluation:
            self._evaluate()

    def _on_training_end(self):
        if not self.history or self.history[-1]['timesteps'] != self.num_timesteps:
            self._evaluate()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--steps', type=int, default=200_000)
    p.add_argument('--output', type=Path, default=Path('models/balance_ppo'))
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--threads', type=int, default=2)
    p.add_argument('--eval-freq', type=int, default=5000)
    p.add_argument('--validation-episodes', type=int, default=10)
    p.add_argument('--validation-first-seed', type=int, default=2000)
    a = p.parse_args()
    if min(a.steps, a.threads, a.eval_freq, a.validation_episodes) < 1:
        p.error('steps, threads, eval-freq, and validation-episodes must be positive')
    output = a.output.with_suffix('') if a.output.suffix == '.zip' else a.output
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(a.threads)
    env = Monitor(BalanceEnv())
    checkpoint = BalanceCheckpoint(output, a.validation_episodes, a.validation_first_seed, a.eval_freq)
    model = PPO('MlpPolicy', env, verbose=1, tensorboard_log='runs', seed=a.seed,
                n_steps=1024, batch_size=128, learning_rate=0.0003,
                ent_coef=0.002, device='cpu')
    try:
        model.learn(total_timesteps=a.steps, callback=checkpoint)
        model.save(str(output) + '.last.zip')
    finally:
        env.close()
    root = Path(__file__).resolve().parent
    sources = ['train.py', 'robot_lab/env.py', 'robot_lab/evaluation.py', 'assets/robot.xml']
    report = {
        'requested_timesteps': a.steps, 'actual_timesteps': model.num_timesteps,
        'training_seed': a.seed, 'selected_timesteps': checkpoint.selected_steps,
        'selection': 'highest validation successes, then mean seconds; earliest on ties',
        'validation_first_seed': a.validation_first_seed,
        'validation_episodes': a.validation_episodes,
        'python': platform.python_version(),
        'packages': {name: version(name) for name in ['mujoco', 'gymnasium', 'stable-baselines3', 'torch', 'numpy']},
        'source_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources},
        'history': checkpoint.history,
    }
    Path(str(output) + '.training.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved best model: {output}.zip (step {checkpoint.selected_steps}); final model: {output}.last.zip')


if __name__ == '__main__':
    main()
