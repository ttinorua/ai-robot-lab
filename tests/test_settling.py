import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from robot_lab.settling import SettlingEnv, settling_reward, selection_score, CHECKPOINT_STEPS, TRAIN_SEEDS
from improve_settling import Selection, acceptance


class TestSettling(unittest.TestCase):
    def test_curriculum_seed_isolation_and_physical_effect(self):
        env=SettlingEnv()
        try:
            for stage in (0,5120):
                env.total_steps=stage
                seen=[]
                for _ in range(36):
                    obs,info=env.reset()
                    self.assertIn(info['reset_seed'],TRAIN_SEEDS)
                    self.assertNotIn(info['reset_seed'],(4008,4009))
                    np.testing.assert_array_equal(obs,env.wrapper.env._obs())
                    self.assertAlmostEqual(np.linalg.norm(env.wrapper.env.data.qpos[3:7]),1.)
                    seen.append(info['perturbation'].get('strength'))
                if stage==0:self.assertNotIn('medium',seen)
                else:self.assertIn('medium',seen)
        finally:env.close()

    def test_reward_targets_observed_lean_and_preserves_fall(self):
        self.assertGreater(settling_reward(0,0,np.zeros(2),False),settling_reward(.803,0,np.zeros(2),False))
        self.assertGreater(settling_reward(.05,.1,np.zeros(2),False),settling_reward(.05,1.,np.zeros(2),False))
        self.assertEqual(settling_reward(0,0,np.zeros(2),True),-20.)
        env=SettlingEnv()
        try:
            env.reset();env.wrapper.env.steps=499
            env.wrapper.env.data.qpos[3:7]=[0,1,0,0]
            _,r,terminated,truncated,_=env.step(np.zeros(2))
            self.assertTrue(terminated);self.assertTrue(truncated);self.assertEqual(r,-20.)
        finally:env.close()

    def test_selection_survival_gate_and_earliest_tie(self):
        def summary(s,r):return {'ppo':dict(successes=s,trials=34,recoveries=r,mean_seconds=9.)}
        self.assertGreater(selection_score(summary(33,1),1.),selection_score(summary(30,30),1.))
        cb=Selection(MagicMock(),MagicMock());cb.reference_rate=1.;cb.model=MagicMock()
        report={'comparisons':{'original':summary(34,2)}}
        with patch('improve_settling.evaluate',return_value=report),patch('improve_settling.save_report'),patch('improve_settling.write'):
            for step in (1024,5120,5120,10240,15360,20480):
                cb.num_timesteps=step;cb.consider()
        self.assertEqual(len(cb.history),4)
        self.assertEqual(cb.selected,5120)
        self.assertEqual(cb.model.save.call_count,1)
        self.assertEqual(CHECKPOINT_STEPS,(5120,10240,15360,20480))

    def test_acceptance_requires_recovery_survival_and_nominal(self):
        s={'ppo':dict(recoveries=1,successes=95,trials=100),'zero':dict(recoveries=0,successes=100,trials=100)}
        report={'comparisons':{'original':s}}
        self.assertTrue(acceptance(report,10));self.assertFalse(acceptance(report,9))
        s['ppo']['successes']=94;self.assertFalse(acceptance(report,10))
        s['ppo']['successes']=100;s['ppo']['recoveries']=0;self.assertFalse(acceptance(report,10))
