"""Finite contact/joint-limit audit and tiny local torque-response interventions."""
import json
import resource
from pathlib import Path
import mujoco
import numpy as np
import torch
from stable_baselines3 import PPO
from controller import Feedback,gain_grid
from engine import Budget,ROOT,rollout,snapshot
from robot_lab.robustness import RobustnessEnv,protocol


def main():
    resource.setrlimit(resource.RLIMIT_CPU,(120,125));torch.set_num_threads(1)
    budget=Budget();budget.check();report=dict(rollouts=[],sign_tests=[],switch_tests=[])
    try:
        original=PPO.load('experiments/balance-checkpoint-selection/policy.zip',device='cpu')
        policies=[('original',original)]+[(p['name'],Feedback(p)) for p in gain_grid()[:4]]
        for seed in (4000,4001):
            for name,policy in policies:
                report['rollouts'].append(dict(controller=name,trial=rollout(policy,protocol()['cases'][0],seed,budget,True)))
        # Matched nominal reset and lifted free-space trials, constant tiny joint torque.
        for lifted in (False,True):
            for tau in (-.02,0.,.02):
                budget.reserve();env=RobustnessEnv(protocol()['cases'][0]);env.reset(4000)
                if lifted:env.env.data.qpos[2]+=1.;mujoco.mj_forward(env.env.model,env.env.data)
                before=snapshot(env.env,np.zeros(2))
                action=np.array([tau/45.,tau/35.])
                env.step(action);mujoco.mj_forward(env.env.model,env.env.data)
                report['sign_tests'].append(dict(lifted=lifted,joint_torque_Nm=tau,before=before,after=snapshot(env.env,action)))
                env.close()
        # Causal intervention on same leaned state: switch only control, never physics.
        for seed in (4000,4001):
            budget.reserve();env=RobustnessEnv(protocol()['cases'][0]);obs=env.reset(seed);frames=[]
            neutral=Feedback(gain_grid()[1])
            for step in range(500):
                policy=original if step<100 else neutral
                action=policy.predict(obs,deterministic=True)[0]
                obs,_,term,trunc,_=env.step(action);mujoco.mj_forward(env.env.model,env.env.data)
                if step%25==0 or step in (99,100,499) or term:frames.append(snapshot(env.env,action))
                if term or trunc:break
            report['switch_tests'].append(dict(seed=seed,switch_at_seconds=2.,before_policy='original',after_policy='hip_PD_8',frames=frames,fall=bool(term)))
            env.close()
    finally:
        (ROOT/'audit.json').write_text(json.dumps(report,indent=2)+'\n');budget.save()
    for row in report['rollouts']:
        t=row['trial'];f=t['final_snapshot']
        print(row['controller'],t['seed'],t['seconds'],'recover',t['recovered_without_later_fall'],'pitch',round(f['pitch'],6),'hips',f['hip_angles'],'torque',f['joint_actuator_torque'],'limits',f['joint_limit_constraints'],'nonfoot',t['nonfoot_contact_fraction'])
    for row in report['sign_tests']:
        print('SIGN',row['lifted'],row['joint_torque_Nm'],'domega_y',row['after']['qvel'][4]-row['before']['qvel'][4],'dhipvel',np.subtract(row['after']['qvel'][6:8],row['before']['qvel'][6:8]).tolist())
    for row in report['switch_tests']:
        print('SWITCH',row['seed'],'fall',row['fall'],'last_pitch',row['frames'][-1]['pitch'],'hips',row['frames'][-1]['hip_angles'])


if __name__=='__main__':main()
