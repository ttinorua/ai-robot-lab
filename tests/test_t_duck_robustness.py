import unittest
import numpy as np
from t_duck_robustness import cases, push_force


class DisturbanceProtocol(unittest.TestCase):
    def test_integrated_push_is_signed_requested_impulse(self):
        for case in cases():
            if "push_impulse" not in case:
                continue
            impulse = sum((push_force(case, tick)*.005 for tick in range(2000)), np.zeros(3))
            expected = np.zeros(3)
            expected[case["push_axis"]] = case["push_impulse"]
            np.testing.assert_allclose(impulse, expected, rtol=0, atol=1e-12)
            self.assertFalse(np.any(push_force(case, 599)))
            self.assertFalse(np.any(push_force(case, 620)))

    def test_cases_cover_both_signs_and_both_push_axes(self):
        pushes = {(c["push_axis"], np.sign(c["push_impulse"])) for c in cases() if "push_impulse" in c}
        self.assertEqual(pushes, {(0,-1),(0,1),(1,-1),(1,1)})
        self.assertEqual(len(cases()), len({c["name"] for c in cases()}))
