"""Postprocess recorded contacts, support geometry and reward/observation semantics."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent


def hull(points):
    pts=sorted(set(tuple(p) for p in points))
    if len(pts)<3:return pts
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lo=[];hi=[]
    for p in pts:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return lo[:-1]+hi[:-1]


def main():
    audit=json.loads((ROOT/'audit.json').read_text());records=[]
    for row in audit['rollouts']:
        t=row['trial'];f=t['final_snapshot'];points=[c['world_position'][:2] for c in f['contacts'] if 'floor' in c['geoms'] and c['force_contact_frame'][0]>1e-6]
        polygon=hull(points);point=f['com'][:2]
        inside=bool(len(polygon)>=3 and all((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])>=-1e-8 for a,b in zip(polygon,polygon[1:]+polygon[:1])))
        errors=[];lags=[];qnorms=[]
        for s in t['snapshots']:
            w,x,y,z=np.array(s['observation'][3:7])/np.linalg.norm(s['observation'][3:7])
            inferred=np.arctan2(2*(x*z+w*y),1-2*(x*x+y*y))
            errors.append(abs(inferred-s['pitch']));qnorms.append(float(np.linalg.norm(s['qpos'][3:7])))
            lags.append(abs(s['termination_upright']-s['torso_matrix'][2][2]))
        records.append(dict(controller=row['controller'],seed=t['seed'],seconds=t['seconds'],success=t['success'],
            final_pitch=f['pitch'],root_height=f['root_height'],hip_angles=f['hip_angles'],limit_constraints=f['joint_limit_constraints'],
            motor_actions=f['action'],joint_torques_Nm=f['joint_actuator_torque'],hip_constraint_torque=f['hip_constraint_torque'],
            contacts=f['contacts'],support_polygon_xy=polygon,com=f['com'],com_inside_support_polygon=inside,
            summed_normal_force_N=sum(c['force_contact_frame'][0] for c in f['contacts']),
            reward=f.get('returned_reward',t['snapshots'][-1]['returned_reward']),steady_reward_components=t['snapshots'][-1]['reward_components'],
            nonfoot_contact_fraction=t['nonfoot_contact_fraction'],max_observed_quaternion_pitch_error=max(errors),
            quaternion_norm_range=[min(qnorms),max(qnorms)],max_termination_kinematic_lag=max(lags)))
    result=dict(records=records,notes=[
        'Support polygon uses contact positions with positive normal force; COM projection in polygon is a static diagnostic, not dynamic stability proof.',
        'efc joint-limit scalar forces act against soft limit penetration; hip qfrc_constraint also includes other constraint contributions.',
        'Snapshot motor_torque field is MuJoCo actuator_force (normalized motor input); joint_actuator_torque is the geared generalized torque.',
        'Original reward already values upright more than lean; the observations do not prove reward is the unique cause of learned lean.',
        'Termination uses height>0.43 and torso Rzz>0.55, allowing tilt up to acos(0.55)=0.9884 rad; original 0.803-rad lean is nominal survival.',
        'mj_step leaves derived kinematics at an intermediate substep; frozen termination/returned reward use this value, while refreshed snapshot and recovery kinematics use final state. No frozen behavior was changed.',
        'Root quaternion is wxyz; observation is nine qpos plus eight qvel, motor hip position [7:9], hip velocity [15:17].'
    ])
    (ROOT/'audit-interpretation.json').write_text(json.dumps(result,indent=2)+'\n')
    for r in records:
        if r['seed']==4000 and r['controller'] in ('original','hip_PD_8'):print(r['controller'],'inside_hull',r['com_inside_support_polygon'],'normal',r['summed_normal_force_N'],'reward_components',r['steady_reward_components'],'obs_pitch_error',r['max_observed_quaternion_pitch_error'],'kinematic_lag',r['max_termination_kinematic_lag'])


if __name__=='__main__':main()
