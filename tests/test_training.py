"""Exercise checkpoint persistence through an actual PPO update."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from stable_baselines3 import PPO


class TestTraining(unittest.TestCase):
    def test_training_saves_loadable_best_and_final_checkpoints(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'policy.test'
            run = subprocess.run(
                [sys.executable, str(root / 'train.py'), '--steps', '1024', '--output', str(output)],
                cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=90,
            )
            self.assertEqual(run.returncode, 0, run.stdout)
            report = json.loads(Path(str(output) + '.training.json').read_text())
            self.assertEqual(report['actual_timesteps'], 1024)
            self.assertEqual(report['selected_timesteps'], 1024)
            self.assertEqual(report['history'][0]['first_seed'], 2000)
            for suffix in ['.zip', '.last.zip']:
                model = PPO.load(str(output) + suffix, device='cpu')
                self.assertEqual(model.num_timesteps, 1024)


if __name__ == '__main__':
    unittest.main()
