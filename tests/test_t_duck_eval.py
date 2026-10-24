"""Acceptance gate checks; real rollout evidence is separate, not mocked here."""
import unittest
import math
import mujoco
import numpy as np

from t_duck_eval import acceptance, advance_physics, MIN_UPRIGHT


class AcceptanceGate(unittest.TestCase):
    def rows(self):
        return [dict(controller="policy", seed=seed, case=case, survived=True,
                     survival_s=10.0, forward_m=1.0)
                for case in ("stand", "forward") for seed in range(10)]

    def test_requires_twenty_paired_full_duration_trials(self):
        rows = self.rows()
        self.assertTrue(acceptance(rows))
        rows[0]["survival_s"] = 9.99
        self.assertFalse(acceptance(rows))

    def test_duplicates_cannot_fill_missing_seed(self):
        rows = self.rows()
        rows[1] = rows[0].copy()
        self.assertFalse(acceptance(rows))

    def test_passive_survival_is_not_walking(self):
        rows = self.rows()
        rows[-1]["forward_m"] = 0.01
        self.assertFalse(acceptance(rows))

    def test_new_state_crossing_fall_boundary_is_visible(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco>
          <option timestep="0.005" gravity="0 0 0"/>
          <worldbody><body pos="0 0 1"><freejoint/>
          <geom type="sphere" size="0.1" mass="1"/>
          <site name="tip" pos="0 0 0.1"/></body></worldbody>
          </mujoco>''')
        data = mujoco.MjData(model)
        angle = math.radians(29)
        data.qpos[3:7] = [math.cos(angle/2), math.sin(angle/2), 0, 0]
        data.qvel[3] = 20.0
        mujoco.mj_forward(model, data)
        self.assertGreater(data.xmat[1].reshape(3, 3)[2, 2], MIN_UPRIGHT)
        advance_physics(model, data)
        quaternion = data.qpos[3:7]
        expected_up = 1 - 2 * (quaternion[1]**2 + quaternion[2]**2)
        self.assertLess(expected_up, MIN_UPRIGHT)
        self.assertAlmostEqual(data.xmat[1].reshape(3, 3)[2, 2], expected_up)
        np.testing.assert_allclose(data.site_xpos[0], data.qpos[:3] + data.xmat[1].reshape(3, 3) @ [0,0,.1])


if __name__ == "__main__":
    unittest.main()
