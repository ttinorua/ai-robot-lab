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

    def _assert_free_fall(self, gravity):
        """Isolate gravity from reset contact impulses, controls and velocity."""
        self.env.reset(seed=42)
        self.env.data.qpos[2] += 1.0
        self.env.data.qvel[:] = 0.0
        self.env.data.ctrl[:] = 0.0
        self.env.model.opt.gravity[:] = gravity
        mujoco.mj_forward(self.env.model, self.env.data)
        self.assertEqual(self.env.data.ncon, 0)
        z0 = float(self.env.data.qpos[2])
        steps = 10
        dt = float(self.env.model.opt.timestep)
        for _ in range(steps):
            mujoco.mj_step(self.env.model, self.env.data)
            self.assertEqual(self.env.data.ncon, 0)
        elapsed = steps * dt
        np.testing.assert_allclose(self.env.data.qvel[:3], gravity * elapsed,
                                   rtol=0, atol=1e-9)
        # Continuous free fall differs from semi-implicit Euler by at most
        # half one acceleration timestep integrated over this interval.
        self.assertAlmostEqual(float(self.env.data.qpos[2]),
                               z0 + 0.5 * gravity[2] * elapsed**2,
                               delta=0.5 * abs(gravity[2]) * dt * elapsed + 1e-9)

    def test_gravity(self):
        gravity = self.env.model.opt.gravity.copy()
        self.assertLess(gravity[2], 0.0)
        self._assert_free_fall(gravity)

    def test_free_fall_tracks_gravity_strength(self):
        gravity = self.env.model.opt.gravity.copy()
        # Counterfactual fields ensure the fixture has no contact/controller
        # kick and that acceleration scales with the configured field.
        for scale in (0.0, 0.5):
            with self.subTest(gravity_scale=scale):
                self._assert_free_fall(gravity * scale)

    def test_motor_response(self):
        self.env.reset(seed=42)
        self.env.step(np.array([0.5, -0.5], dtype=np.float32))
        self.assertTrue(np.allclose(self.env.data.ctrl, [0.5, -0.5]))

if __name__ == '__main__':
    unittest.main()
