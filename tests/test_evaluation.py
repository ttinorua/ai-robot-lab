"""Regression coverage for the reported policy and evaluation protocol."""
from pathlib import Path
import unittest

import torch
from stable_baselines3 import PPO
from robot_lab.evaluation import evaluate_policy


class TestEvaluation(unittest.TestCase):
    def test_verified_policy_survives_ten_trials(self):
        torch.set_num_threads(2)
        path = Path(__file__).resolve().parents[1] / 'experiments/balance-checkpoint-selection/policy.zip'
        result = evaluate_policy(PPO.load(path, device='cpu'), episodes=10, first_seed=1000)
        self.assertEqual(result['successes'], 10)
        self.assertEqual(result['mean_seconds'], 10.0)
        self.assertEqual([trial['seed'] for trial in result['trials']], list(range(1000, 1010)))
        self.assertTrue(all(t['truncated'] and not t['terminated'] for t in result['trials']))

    def test_empty_evaluation_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_policy(None, episodes=0)


if __name__ == '__main__':
    unittest.main()
