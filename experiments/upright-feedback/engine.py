"""Measured kinematics/contact instrumentation around the immutable benchmark."""
import hashlib
import json
from pathlib import Path
import time

import mujoco
import numpy as np
from robot_lab.robustness import RobustnessEnv, RecoveryTracker, success

ROOT=Path(__file__).resolve().parent


class Budget:
    def __init__(self):
        self.path=ROOT/'budget.json'
        self.state=json.loads(self.path.read_text())
        self.cpu_start=time.process_time(); self.prior=self.state['cpu_seconds']

    def check(self):
        if self.prior+time.process_time()-self.cpu_start>550 or time.time()-self.state['wall_start_unix']>1140:
            raise RuntimeError('Whole milestone CPU/wall guard reached')

    def reserve(self):
        self.check()
        if self.state['rollouts']>=2800:raise RuntimeError('Rollout budget exhausted')
        self.state['rollouts']+=1;self.save()

    def save(self):
        data=dict(self.state,cpu_seconds=self.prior+time.process_time()-self.cpu_start,
                  wall_seconds=time.time()-self.state['wall_start_unix'])
        self.path.write_text(json.dumps(data,indent=2)+'\n')


def snapshot(env, action):
    m,d=env.model,env.data
    mat=d.body('torso').xmat.reshape(3,3)
    contacts=[]; nonfoot=False
    for c in d.contact[:d.ncon]:
        names=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) or f'unnamed_geom_{g}' for g in (c.geom1,c.geom2)]
        force=np.zeros(6);mujoco.mj_contactForce(m,d,len(contacts),force)
        contacts.append(dict(geoms=names,world_position=c.pos.tolist(),distance=float(c.dist),force_contact_frame=force.tolist(),frame=c.frame.reshape(3,3).tolist()))
        if 'floor' in names and not any(n in ('left_foot','right_foot') for n in names):nonfoot=True
    support=[c['world_position'][:2] for c in contacts if 'floor' in c['geoms']]
    com=d.subtree_com[m.body('torso').id].tolist()
    bounds=[np.min(support,axis=0).tolist(),np.max(support,axis=0).tolist()] if support else None
    return dict(seconds=float(d.time),qpos=d.qpos.tolist(),qvel=d.qvel.tolist(),
                observation=env._obs().tolist(),root_height=float(d.qpos[2]),
                torso_matrix=mat.tolist(),tilt=float(np.arccos(np.clip(mat[2,2],-1,1))),
                pitch=float(np.arctan2(mat[0,2],mat[2,2])),angular_speed=float(np.linalg.norm(d.qvel[3:6])),
                action=np.asarray(action).tolist(),motor_torque=d.actuator_force.tolist(),
                joint_actuator_torque=d.qfrc_actuator[6:8].tolist(),hip_angles=d.qpos[7:9].tolist(),
                com=com,support_xy_bounds=bounds,contacts=contacts,nonfoot_floor_contact=nonfoot,
                hip_constraint_torque=d.qfrc_constraint[6:8].tolist(),
                joint_limit_constraints=[dict(index=i,object_id=int(d.efc_id[i]),force=float(d.efc_force[i]),position=float(d.efc_pos[i])) for i in range(d.nefc) if d.efc_type[i]==int(mujoco.mjtConstraint.mjCNSTR_LIMIT_JOINT)])


def rollout(policy,case,seed,budget,trace=False):
    budget.reserve(); wrapper=RobustnessEnv(case)
    try:
        obs=wrapper.reset(seed); initial=wrapper.initial_evidence
        state_hash=hashlib.sha256(np.array(initial['after']['qpos']+initial['after']['qvel'],dtype=np.float64).tobytes()).hexdigest()
        tracker=RecoveryTracker(1.1 if case['kind']=='push' else 0.)
        effort=0.; saturated=nonfoot=band=0; max_tilt=0.; tilt_sum=speed_sum=0.; snapshots=[]
        for step in range(500):
            budget.check()
            action=np.zeros(2) if policy is None else policy.predict(obs,deterministic=True)[0]
            previous=wrapper.env.previous_action.copy()
            obs,reward,terminated,truncated,info=wrapper.step(action)
            if not np.isfinite(obs).all() or not np.isfinite(reward):raise RuntimeError('Nonfinite simulator state')
            mujoco.mj_forward(wrapper.env.model,wrapper.env.data)
            d=wrapper.env.data; tilt=float(np.arccos(np.clip(d.body('torso').xmat[8],-1,1)))
            speed=float(np.linalg.norm(d.qvel[3:6])); tracker.update(step,tilt,speed,terminated)
            effort+=float(np.sum(np.square(action)))*.02
            saturated+=int(np.any(np.abs(action)>=.999)); max_tilt=max(max_tilt,tilt)
            tilt_sum+=tilt;speed_sum+=speed;band+=int(tilt<=.1 and speed<=.3)
            nf=False
            for c in d.contact[:d.ncon]:
                names=[wrapper.env.model.geom(int(g)).name for g in (c.geom1,c.geom2)]
                if 'floor' in names and not any(n in ('left_foot','right_foot') for n in names):nf=True
            nonfoot+=int(nf)
            if trace and (step%25==0 or step in (49,50,54,55,499) or terminated):
                snap=snapshot(wrapper.env,action)
                components=dict(alive=2.,upright=4.*info['upright'],height=-2.*abs(info['height']-.675),angular=-.25*speed,effort=-.08*float(np.sum(np.square(action))),change=-.06*float(np.sum(np.square(action-previous)))) if not terminated else dict(fall=-10.)
                snap.update(reward_components=components,returned_reward=float(reward),reward_component_sum=float(sum(components.values())),termination_upright=info['upright'],termination_height=info['height'])
                snapshots.append(snap)
            if terminated or truncated:break
        else:raise RuntimeError('Missing horizon termination')
        n=step+1
        result=dict(seed=seed,perturbation=case,initial_state_sha256=state_hash,reset_evidence=initial,
                    push_evidence=wrapper.push_evidence,actual_impulse_Ns=sum(e['integrated_impulse_Ns'] for e in wrapper.push_evidence),
                    seconds=info['survived_seconds'],success=success(terminated,truncated),terminated=bool(terminated),truncated=bool(truncated),
                    recovery_window_seconds=tracker.latency,recovered_without_later_fall=bool(tracker.latency is not None and not terminated),
                    action_squared_integral=effort,peak_torso_tilt_rad=max_tilt,mean_tilt_rad=tilt_sum/n,mean_angular_speed=speed_sum/n,
                    saturation_fraction=saturated/n,nonfoot_contact_fraction=nonfoot/n,recovery_band_fraction=band/n,
                    snapshots=snapshots)
        result['final_snapshot']=snapshot(wrapper.env,action)
        result['final_in_band']=bool(tilt<=.1 and speed<=.3)
        return result
    finally:wrapper.close();budget.save()


def totals(rows):
    return dict(trials=len(rows),survivals=sum(r['success'] for r in rows),recoveries=sum(r['recovered_without_later_fall'] for r in rows),
                mean_seconds=float(np.mean([r['seconds'] for r in rows])),mean_tilt_rad=float(np.mean([r['mean_tilt_rad'] for r in rows])),
                mean_effort=float(np.mean([r['action_squared_integral'] for r in rows])),
                mean_nonfoot_contact_fraction=float(np.mean([r['nonfoot_contact_fraction'] for r in rows])),
                mean_saturation_fraction=float(np.mean([r['saturation_fraction'] for r in rows])))


def rank(summary):
    # No non-foot ground-bracing may win over an equally surviving upright controller.
    return (summary['recoveries'],summary['survivals'],-summary['mean_nonfoot_contact_fraction'],summary['mean_seconds'],-summary['mean_effort'])
