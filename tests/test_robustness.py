import unittest
from unittest.mock import patch

import mujoco
import numpy as np
from robot_lab import BalanceEnv
from robot_lab.robustness import Budget, RobustnessEnv, protocol, success, trial, summarize, RecoveryTracker


class TestRobustness(unittest.TestCase):
    def test_reset_effect_normalization_and_pairing(self):
        for case in protocol()['cases']:
            a, b = RobustnessEnv(case), BalanceEnv()
            try:
                original, _ = b.reset(seed=41000)
                obs = a.reset(41000)
                qpos, qvel = a.env.data.qpos, a.env.data.qvel
                self.assertAlmostEqual(np.linalg.norm(qpos[3:7]), 1.)
                np.testing.assert_array_equal(obs, a.env._obs())
                if case['kind'] == 'pitch':
                    self.assertAlmostEqual(a.env.data.body('torso').xmat[2], np.sin(case['value']))
                    self.assertFalse(np.array_equal(obs, original))
                    np.testing.assert_array_equal(qvel, b.data.qvel)
                elif case['kind'] in ('linear_velocity', 'angular_velocity'):
                    index = 0 if case['kind'] == 'linear_velocity' else 4
                    expected = b.data.qvel.copy()
                    expected[index] += case['value']
                    np.testing.assert_allclose(qvel, expected, atol=0, rtol=0)
                    np.testing.assert_array_equal(qpos, b.data.qpos)
                else:
                    np.testing.assert_array_equal(obs, original)
                np.testing.assert_array_equal(a.reset(41000), obs)
                other = RobustnessEnv(case)
                try:
                    np.testing.assert_array_equal(other.reset(41000), obs)
                finally:
                    other.close()
            finally:
                a.close()
                b.close()

    def test_push_substeps_timing_strength_direction_and_clearing(self):
        native_step = mujoco.mj_step
        for case in protocol()['cases']:
            if case['kind'] != 'push':
                continue
            wrapper = RobustnessEnv(case)
            try:
                wrapper.reset(41001)
                env = wrapper.env
                calls = []
                def observe(model, data):
                    calls.append((env.steps, data.xfrc_applied.copy()))
                    native_step(model, data)
                with patch('mujoco.mj_step', side_effect=observe):
                    for _ in range(57):
                        wrapper.step(np.zeros(2))
                        self.assertFalse(env.data.xfrc_applied.any())
                self.assertEqual(len(calls), 114)
                for step, forces in calls:
                    expected = np.zeros_like(forces)
                    if 50 <= step < 55:
                        expected[env.model.body('torso').id, 0] = case['value'] / .1
                    np.testing.assert_array_equal(forces, expected)
                self.assertEqual([e['step'] for e in wrapper.push_evidence], list(range(50, 55)))
                self.assertAlmostEqual(sum(e['integrated_impulse_Ns'] for e in wrapper.push_evidence), case['value'])
                wrapper.reset(41002)
                self.assertEqual(wrapper.push_evidence, [])
                self.assertFalse(env.data.xfrc_applied.any())
                self.assertEqual(env.steps, 0)
            finally:
                wrapper.close()

    def test_push_changes_simulated_momentum(self):
        for value in (-1.5, -.5, .5, 1.5):
            a = RobustnessEnv(dict(kind='push', value=value))
            b = RobustnessEnv(dict(kind='nominal', value=0))
            try:
                for wrapper in (a, b):
                    wrapper.reset(41003)
                    wrapper.env.data.qpos[2] += 3
                    wrapper.env.steps = 50
                    mujoco.mj_forward(wrapper.env.model, wrapper.env.data)
                for _ in range(5):
                    a.step(np.zeros(2))
                    b.step(np.zeros(2))
                for wrapper in (a, b):
                    mujoco.mj_forward(wrapper.env.model, wrapper.env.data)
                    mujoco.mj_subtreeVel(wrapper.env.model, wrapper.env.data)
                momentum_delta = mujoco.mj_getTotalmass(a.env.model) * (a.env.data.subtree_linvel[0, 0] - b.env.data.subtree_linvel[0, 0])
                self.assertAlmostEqual(momentum_delta, value, delta=abs(value) * .002)
            finally:
                a.close()
                b.close()

    def test_force_cleared_on_error(self):
        wrapper = RobustnessEnv(dict(kind='push', value=.5))
        try:
            wrapper.reset(41004)
            wrapper.env.steps = 50
            with patch.object(wrapper.env, 'step', side_effect=RuntimeError('injected')):
                with self.assertRaises(RuntimeError):
                    wrapper.step(np.zeros(2))
            self.assertFalse(wrapper.env.data.xfrc_applied.any())
        finally:
            wrapper.close()

    def test_deterministic_pairing_and_no_leakage(self):
        case = protocol()['cases'][-1]
        budget = Budget()
        first = trial(None, case, 41005, budget)
        trial(None, protocol()['cases'][1], 41006, budget)
        self.assertEqual(first, trial(None, case, 41005, budget))
        result = summarize([dict(seed=41005, ppo=first, zero=first)])
        self.assertEqual(result['paired_seconds']['bootstrap_95_percent'], [0., 0.])
        self.assertEqual(first['action_squared_integral'], 0.)

    def test_fall_at_horizon_is_failure(self):
        wrapper = RobustnessEnv(dict(kind='nominal', value=0))
        try:
            wrapper.reset(41007)
            wrapper.env.steps = 499
            wrapper.env.data.qpos[2] = 1.5
            wrapper.env.data.qpos[3:7] = [0, 1, 0, 0]
            mujoco.mj_forward(wrapper.env.model, wrapper.env.data)
            _, _, terminated, truncated, _ = wrapper.step(np.zeros(2))
            self.assertTrue(terminated)
            self.assertTrue(truncated)
            self.assertFalse(success(terminated, truncated))
        finally:
            wrapper.close()

    def test_budget_rejects_before_episode(self):
        for budget in (Budget(1450), Budget(cpu_seconds=841)):
            with self.assertRaises(RuntimeError):
                budget.reserve()


    def test_recovery_requires_continuous_window_after_push(self):
        tracker = RecoveryTracker(1.1)
        for step in range(79):
            tracker.update(step, .01, .01, False)
        self.assertIsNone(tracker.latency)  # Only 24 eligible intervals.
        tracker.update(79, .01, .31, False)  # High angular speed resets streak.
        for step in range(80, 104):
            tracker.update(step, .01, .01, False)
        self.assertIsNone(tracker.latency)
        tracker.update(104, .01, .01, False)
        self.assertAlmostEqual(tracker.latency, 1.0)
        fallen = RecoveryTracker(0)
        for step in range(25):
            fallen.update(step, .01, .01, True)
        self.assertIsNone(fallen.latency)
        tilted = RecoveryTracker(0)
        for step in range(25):
            tilted.update(step, .11, .01, False)
        self.assertIsNone(tilted.latency)

    def test_wrapper_nominal_trajectory_matches_original(self):
        wrapper = RobustnessEnv(dict(kind='nominal', value=0))
        original = BalanceEnv()
        try:
            obs = wrapper.reset(41008)
            np.testing.assert_array_equal(obs, original.reset(seed=41008)[0])
            for _ in range(500):
                a, b = wrapper.step(np.zeros(2)), original.step(np.zeros(2))
                np.testing.assert_array_equal(a[0], b[0])
                self.assertEqual(a[1:], b[1:])
                if a[2] or a[3]:
                    break
        finally:
            wrapper.close()
            original.close()
