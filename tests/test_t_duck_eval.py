"""Acceptance gate checks; real rollout evidence is separate, not mocked here."""
import unittest

from t_duck_eval import acceptance


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


if __name__ == "__main__":
    unittest.main()
