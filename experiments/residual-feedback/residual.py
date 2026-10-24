"""Fresh Gymnasium adaptation of published additive residual-control architecture.

Johannink et al. 1812.03201v2; Silver/Allen RPL. See SOURCES.md for provenance.
No external implementation is imported, installed or copied into this module.
"""
import importlib.util
import json
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
import torch
from stable_baselines3 import PPO
from robot_lab.robustness import RobustnessEnv, protocol

ROOT=Path(__file__).resolve().parent
BASE_ROOT=ROOT.parent/'upright-feedback'

def load_local(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

feedback=load_local('frozen_upright_controller',BASE_ROOT/'controller.py')
engine=load_local('frozen_upright_engine',BASE_ROOT/'engine.py')
PARAMETERS=json.loads((BASE_ROOT/'selected.json').read_text())['parameters']
GEARS=np.array([45.,35.]);RESIDUAL_LIMIT=.10
TRAIN_SEEDS=tuple(range(4000,4008));VALIDATION_SEEDS=(4008,4009)
VALIDATION_NAMES=('nominal','pitch_medium_+1','linear_velocity_medium_-1','push_medium_-1','push_medium_+1')
CHECKPOINT_STEPS=(8192,16384,24576,32768)


def compose(observation,residual_action):
    base,_=feedback.Feedback(PARAMETERS).predict(observation)
    raw=np.asarray(residual_action,dtype=float)
    if raw.shape!=(2,) or not np.isfinite(raw).all():raise ValueError('Finite two-dimensional residual required')
    normalized=np.clip(raw,-1,1);delta=RESIDUAL_LIMIT*normalized
    base_torque=base.astype(float)*GEARS
    requested=base_torque+delta
    total=np.clip(requested,-GEARS,GEARS)
    action=(total/GEARS).astype(np.float32)
    return action,dict(base_action=base.tolist(),base_torque_Nm=base_torque.tolist(),
        raw_residual=raw.tolist(),residual_torque_Nm=delta.tolist(),total_torque_Nm=total.tolist(),
        residual_clipped=bool(np.any(raw!=normalized)),total_clipped=bool(np.any(total!=requested)))


def pose(obs):
    o=np.asarray(obs);q=o[3:7]/np.linalg.norm(o[3:7]);w,x,y,z=q
    return float(np.arccos(np.clip(1-2*(x*x+y*y),-1,1))),float(np.linalg.norm(o[12:15]))


def reward_for(obs,residual,action,fallen):
    if fallen:return -20.
    tilt,speed=pose(obs)
    return float(1.+2.*np.exp(-(tilt/.1)**2)-2.*tilt**2-.1*speed**2
                 -.05*np.sum(np.square(np.clip(residual,-1,1)))-.01*np.sum(np.square(action))
                 +1.*(tilt<=.1 and speed<=.3))


class DisturbanceEnv(gym.Env):
    def __init__(self,training=True,case=None):
        self.native=RobustnessEnv(case or protocol()['cases'][0]);self.training=training
        self.action_space=self.native.env.action_space;self.observation_space=self.native.env.observation_space
        self.episode=0;self.seed_log=[]

    def reset(self,seed=None,options=None):
        super().reset(seed=seed)
        if self.training:
            cases=protocol()['cases'];self.native.case=cases[self.episode%len(cases)]
            seed=TRAIN_SEEDS[self.episode%len(TRAIN_SEEDS)];self.episode+=1
        elif seed is None:raise ValueError('Evaluation requires explicit seed')
        self.seed_log.append(seed)
        obs=self.native.reset(seed)
        return obs,dict(reset_seed=seed)

    def step(self,action):
        result=self.native.step(action)
        # Match the immutable instrumented evaluator's post-integration refresh.
        mujoco.mj_forward(self.native.env.model,self.native.env.data)
        return result

    def close(self):self.native.close()


class ResidualActionWrapper(gym.ActionWrapper):
    def __init__(self,env):
        super().__init__(env);self.observation=None;self.last_composition=None
        self.steps_seen=0;self.residual_clip_steps=0;self.total_clip_steps=0

    def reset(self,**kwargs):
        obs,info=self.env.reset(**kwargs);self.observation=obs.copy();return obs,info

    def action(self,residual):
        if self.observation is None:raise RuntimeError('Reset before action')
        total,details=compose(self.observation,residual);self.last_composition=details
        self.steps_seen+=1;self.residual_clip_steps+=details['residual_clipped'];self.total_clip_steps+=details['total_clipped']
        return total

    def step(self,residual):
        total=self.action(residual);obs,_,terminated,truncated,info=self.env.step(total)
        reward=reward_for(obs,residual,total,terminated)
        self.observation=obs.copy()
        return obs,reward,terminated,truncated,dict(info,composition=self.last_composition)


def new_model(env,seed=83):
    model=PPO('MlpPolicy',env,n_steps=1024,batch_size=128,n_epochs=10,learning_rate=1e-4,
              ent_coef=0.,gamma=.99,gae_lambda=.95,clip_range=.2,device='cpu',seed=seed,
              policy_kwargs=dict(log_std_init=float(np.log(.05))),verbose=0)
    with torch.no_grad():model.policy.action_net.weight.zero_();model.policy.action_net.bias.zero_()
    return model


class ResidualController:
    def __init__(self,model=None):self.model=model;self.reset_stats()
    def reset_stats(self):
        self.steps=0;self.residual_clip_steps=0;self.total_clip_steps=0;self.residual_effort=0.;self.samples=[]
    def predict(self,observation,deterministic=True):
        if self.model is None:raw=np.zeros(2)
        else:
            tensor,_=self.model.policy.obs_to_tensor(observation)
            with torch.no_grad():actions,_,_=self.model.policy(tensor,deterministic=deterministic)
            raw=actions.cpu().numpy().reshape(2)
        total,details=compose(observation,raw);self.steps+=1
        self.residual_clip_steps+=details['residual_clipped'];self.total_clip_steps+=details['total_clipped']
        self.residual_effort+=float(np.sum(np.square(details['residual_torque_Nm'])))*.02
        if self.steps==1 or self.steps%50==0:self.samples.append(dict(step=self.steps,**details))
        return total,None
    def stats(self):
        return dict(residual_clip_steps=self.residual_clip_steps,total_clip_steps=self.total_clip_steps,
                    residual_effort_Nm_squared_seconds=self.residual_effort,composition_samples=self.samples)
