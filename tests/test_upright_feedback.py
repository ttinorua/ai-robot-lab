import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

EXPERIMENT=Path(__file__).resolve().parents[1]/'experiments/upright-feedback'
# Unique module names prevent accidental import of other experiment modules.
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,EXPERIMENT/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
controller=module('upright_controller','controller.py')
engine=module('upright_engine','engine.py')


class TestUprightFeedback(unittest.TestCase):
    def obs(self):
        a=np.zeros(17);a[2]=.675;a[3]=1.;return a

    def test_sign_gearing_clipping_and_input_discipline(self):
        obs=self.obs();obs[7:9]=.1
        model=controller.Feedback(dict(hip_k=8.))
        action,_=model.predict(obs)
        np.testing.assert_allclose(action*np.array([45,35]),[-.8,-.8],rtol=1e-6)
        pitched=self.obs();pitched[3]=np.cos(.05);pitched[5]=np.sin(.05)
        action,_=controller.Feedback(dict(pitch_k=8)).predict(pitched)
        self.assertTrue(np.all(action>0))
        big=self.obs();big[7:9]=100
        np.testing.assert_array_equal(model.predict(big)[0],[-1,-1])
        np.testing.assert_array_equal(model.predict(obs)[0],model.predict(obs.copy())[0])
        for bad in (np.zeros(18),np.full(17,np.nan),np.zeros(17)):
            with self.assertRaises(ValueError):model.predict(bad)
        # No clock, scenario, seed, simulator object or future impulse is an input.
        self.assertEqual(list(__import__('inspect').signature(model.predict).parameters),['observation','deterministic'])

    def test_grid_and_seed_selection_isolation(self):
        grid=controller.gain_grid();self.assertEqual(len(grid),32)
        from unittest.mock import patch
        with patch.dict(sys.modules,{'controller':controller,'engine':engine}):
            runner=module('upright_runner','run.py')
        a=dict(trials=2,survivals=2,recoveries=2,mean_seconds=10.,mean_effort=1.,mean_nonfoot_contact_fraction=0.)
        b=dict(a,recoveries=0,mean_effort=0.)
        records=[dict(summary=b,seed=4000),dict(summary=a,seed=4003)]
        self.assertEqual(runner.choose(records),[1,0])
        records[0]['holdout_result']=dict(recoveries=10000)
        self.assertEqual(runner.choose(records),[1,0])
        summary=dict(trials=10,survivals=9,recoveries=8)
        report=dict(summaries=dict(candidate=summary,original=dict(recoveries=0),zero=dict(recoveries=2)))
        self.assertTrue(runner.gate(report,10));self.assertFalse(runner.gate(report,9))
        report['summaries']['zero']['recoveries']=8
        self.assertFalse(runner.gate(report,10))

    def test_nominal_trial_matches_frozen_evaluation_and_upright_pd(self):
        from robot_lab.robustness import trial,Budget,protocol
        class Counter:
            def reserve(self):pass
            def check(self):pass
            def save(self):pass
        nominal=protocol()['cases'][0]
        old=trial(None,nominal,41020,Budget())
        new=engine.rollout(None,nominal,41020,Counter())
        for key in ('seconds','success','terminated','truncated','recovery_window_seconds','initial_state_sha256','actual_impulse_Ns'):
            self.assertEqual(old[key],new[key])
        pd=engine.rollout(controller.Feedback(dict(hip_k=8.,hip_d=1.)),nominal,41021,Counter(),True)
        self.assertTrue(pd['success']);self.assertTrue(pd['recovered_without_later_fall'])
        self.assertTrue(pd['final_in_band']);self.assertEqual(pd['nonfoot_contact_fraction'],0.)
        for snap in pd['snapshots']:
            self.assertAlmostEqual(snap['reward_component_sum'],snap['returned_reward'],places=6)
