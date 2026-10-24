"""Evaluate deterministic policies on explicit, reproducible reset seeds."""
import argparse
import hashlib
import json
from pathlib import Path

from stable_baselines3 import PPO
from robot_lab.evaluation import evaluate_policy


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='models/balance_ppo.zip')
    p.add_argument('--episodes', type=int, default=10)
    p.add_argument('--first-seed', type=int, default=1000)
    p.add_argument('--controller', choices=['ppo', 'zero'], default='ppo')
    p.add_argument('--render', action='store_true')
    p.add_argument('--json', type=Path)
    p.add_argument('--require-all-success', action='store_true')
    a = p.parse_args()
    if a.episodes < 1:
        p.error('--episodes must be positive')
    policy = PPO.load(a.model, device='cpu') if a.controller == 'ppo' else None
    result = evaluate_policy(policy, a.episodes, a.first_seed, a.render)
    result['controller'] = a.controller
    if policy is not None:
        model_path = Path(a.model)
        if not model_path.is_file():
            model_path = Path(str(model_path) + '.zip')
        result['model_sha256'] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    for episode in result['trials']:
        print(f"Seed {episode['seed']}: {episode['seconds']:.2f}s | success={episode['success']}")
    print(f"Average: {result['mean_seconds']:.2f}s | 10-second success: {result['successes']}/{a.episodes}")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(result, indent=2) + '\n')
    if a.require_all_success and result['successes'] != a.episodes:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
