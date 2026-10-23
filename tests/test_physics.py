import unittest
import numpy as np
import mujoco
from robot_lab import BalanceEnv

class TestPhysics(unittest.TestCase):
    def setUp(self):
        self.env = BalanceEnv()

    def tearDown(self):
        self.env.close()

    def test_model_loads(self):
        self.assertEqual(self.env.model.nu, 2)
        self.assertGreater(self.env.model.nbody, 2)

    def test_reset_observation(self):
        obs, info = self.env.reset(seed=42)
        self.assertEqual(obs.shape, (17,))
        self.assertTrue(np.isfinite(obs).all())
        self.assertTrue(self.env.observation_space.contains(obs))

    def test_step_interface(self):
        self.env.reset(seed=42)
        obs, reward, terminated, truncated, info = self.env.step(np.zeros(2, dtype=np.float32))
        self.assertTrue(self.env.observation_space.contains(obs))
        self.assertTrue(np.isfinite(reward))
        self.assertIsInstance(terminated, bool)
        self.assertIsInstance(truncated, bool)
        self.assertIn('height', info)
        self.assertIn('upright', info)

    def test_gravity(self):
        self.env.reset(seed=42)
        # Isolate free fall from contact forces: the normal reset rests on feet.
        self.env.data.qpos[2] += 1.0
        mujoco.mj_forward(self.env.model, self.env.data)
        self.assertEqual(self.env.data.ncon, 0)
        z0 = float(self.env.data.qpos[2])
        for _ in range(5):
            self.env.step(np.zeros(2, dtype=np.float32))
        self.assertLess(float(self.env.data.qpos[2]), z0)

    def test_time_limit_is_not_a_fall(self):
        self.env.reset(seed=42)
        self.env.steps = 499
        _, _, terminated, truncated, info = self.env.step(np.zeros(2, dtype=np.float32))
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual(info['survived_seconds'], 10.0)

    def test_fall_at_time_limit_is_still_a_failure(self):
        self.env.reset(seed=42)
        self.env.data.qpos[2] = 1.5
        self.env.data.qpos[3:7] = [0, 1, 0, 0]  # Upside down, clear of the floor.
        mujoco.mj_forward(self.env.model, self.env.data)
        self.env.steps = 499
        _, _, terminated, truncated, _ = self.env.step(np.zeros(2, dtype=np.float32))
        self.assertTrue(terminated)
        self.assertTrue(truncated)

    def test_motor_response(self):
        self.env.reset(seed=42)
        self.env.step(np.array([0.5, -0.5], dtype=np.float32))
        self.assertTrue(np.allclose(self.env.data.ctrl, [0.5, -0.5]))

if __name__ == '__main__':
    unittest.main()
