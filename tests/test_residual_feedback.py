import importlib.util
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from robot_lab.robustness import RobustnessEnv,protocol

ROOT=Path(__file__).resolve().parents[1]/'experiments/residual-feedback'
spec=importlib.util.spec_from_file_location('robot_lab_residual',ROOT/'residual.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


class TestResidualFeedback(unittest.TestCase):
    def test_zero_residual_exact_full_trajectories(self):
        for case in [protocol()['cases'][0],protocol()['cases'][4],protocol()['cases'][-2]]:
            a=RobustnessEnv(case);b=r.ResidualActionWrapper(r.DisturbanceEnv(training=False,case=case))
            try:
                x=a.reset(41040);y=b.reset(seed=41040)[0];np.testing.assert_array_equal(x,y)
                for _ in range(500):
                    base=r.feedback.Feedback(r.PARAMETERS).predict(x)[0]
                    z=r.compose(y,np.zeros(2))[0];np.testing.assert_array_equal(base,z)
                    u=a.step(base);v=b.step(np.zeros(2))
                    import mujoco
                    mujoco.mj_forward(a.env.model,a.env.data)
                    np.testing.assert_array_equal(u[0],v[0]);self.assertEqual(u[2:4],v[2:4])
                    x,y=u[0],v[0]
                    if u[2] or u[3]:break
            finally:a.close();b.close()

    def test_physical_sign_gear_clipping_and_input_discipline(self):
        obs=np.zeros(17);obs[2]=.675;obs[3]=1
        base=r.feedback.Feedback(r.PARAMETERS).predict(obs)[0]
        action,info=r.compose(obs,[1.,-1.])
        np.testing.assert_allclose((action-base)*[45,35],[.1,-.1],rtol=1e-6)
        _,info=r.compose(obs,[2.,-3.]);self.assertTrue(info['residual_clipped'])
        with patch.object(r.feedback.Feedback,'predict',return_value=(np.array([1.,-1.]),None)):
            total,info=r.compose(obs,[1.,-1.]);np.testing.assert_array_equal(total,[1.,-1.]);self.assertTrue(info['total_clipped'])
        for bad in ([np.nan,0],[0,np.inf],[1,2,3]):
            with self.assertRaises(ValueError):r.compose(obs,bad)
        for bad_obs in (np.zeros(18),np.full(17,np.nan),np.zeros(17)):
            with self.assertRaises(ValueError):r.compose(bad_obs,[0,0])

    def test_seed_separation_and_common_composition(self):
        env=r.ResidualActionWrapper(r.DisturbanceEnv(training=True))
        try:
            for _ in range(20):
                obs,info=env.reset(seed=7000)
                self.assertIn(info['reset_seed'],range(4000,4008))
                expected,_=r.compose(obs,[.2,-.3]);np.testing.assert_array_equal(env.action([.2,-.3]),expected)
            self.assertEqual(r.VALIDATION_SEEDS,(4008,4009))
        finally:env.close()

    def test_zero_mean_serialization_and_ppo_collect_rollouts(self):
        torch.set_num_threads(1);wrapped=r.ResidualActionWrapper(r.DisturbanceEnv(training=True))
        model=r.new_model(wrapped)
        obs=wrapped.reset()[0]
        np.testing.assert_array_equal(model.predict(obs,deterministic=True)[0],[0,0])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'untrained.zip';model.save(path);loaded=PPO.load(path,device='cpu')
            np.testing.assert_array_equal(r.ResidualController(model).predict(obs)[0],r.ResidualController(loaded).predict(obs)[0])
            self.assertAlmostEqual(float(loaded.policy.log_std.exp()[0].detach()),.05,places=6)
        # Collect four transitions without calling learn/train: confirm PPO's forward path goes through wrapper.
        _,callback=model._setup_learn(4,callback=None,reset_num_timesteps=True,tb_log_name='test')
        callback.on_training_start({},{});before=wrapped.steps_seen
        self.assertTrue(model.collect_rollouts(model.env,callback,model.rollout_buffer,n_rollout_steps=4))
        self.assertEqual(wrapped.steps_seen-before,4)
        final=wrapped.last_composition
        applied=wrapped.env.native.env.data.ctrl
        expected=np.array(final['total_torque_Nm'])/r.GEARS
        np.testing.assert_allclose(applied,expected,rtol=1e-6,atol=1e-8)
        self.assertEqual(model.num_timesteps,4);wrapped.close()


    def test_selection_and_no_loss_gain_gate(self):
        spec=importlib.util.spec_from_file_location('robot_lab_residual_runner',ROOT/'run.py');runner=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'residual':r}):spec.loader.exec_module(runner)
        base=dict(survivals=10,recoveries=9,mean_seconds=10.)
        self.assertGreater(runner.score(dict(survivals=10,recoveries=9,mean_seconds=10.),base),runner.score(dict(survivals=9,recoveries=9,mean_seconds=9.),base))
        report=dict(summaries=dict(base=base,candidate=dict(survivals=10,recoveries=10)))
        self.assertTrue(runner.gate(report,10));self.assertFalse(runner.gate(report,9))
        report['summaries']['candidate']['survivals']=9;self.assertFalse(runner.gate(report,10))
        report['summaries']['candidate']=dict(survivals=10,recoveries=9);self.assertFalse(runner.gate(report,10))
