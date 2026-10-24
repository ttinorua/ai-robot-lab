import csv, json, time
from pathlib import Path
import mujoco,numpy as np,torch
from stable_baselines3 import PPO
from robot_lab.robustness import RobustnessEnv,protocol
root=Path('experiments/settling-candidate'); start=time.process_time(); wall=time.monotonic()
torch.set_num_threads(1)
policy=PPO.load('experiments/balance-checkpoint-selection/policy.zip',device='cpu')
rows=[]; summaries=[]
cases=[c for c in protocol()['cases'] if c['name'] in ['nominal','pitch_medium_-1','linear_velocity_medium_-1','angular_velocity_medium_+1','push_medium_-1','push_medium_+1']]
for case in cases:
 for name,controller in [('original',policy),('zero',None)]:
  env=RobustnessEnv(case); obs=env.reset(4000); trace=[]
  for step in range(500):
   action=np.zeros(2) if controller is None else controller.predict(obs,deterministic=True)[0]
   obs,_,terminated,truncated,info=env.step(action)
   mujoco.mj_forward(env.env.model,env.env.data)
   mat=env.env.data.body('torso').xmat.reshape(3,3)
   row=dict(case=case['name'],controller=name,seed=4000,seconds=(step+1)*.02,tilt=float(np.arccos(np.clip(mat[2,2],-1,1))),pitch=float(np.arctan2(mat[0,2],mat[2,2])),angular_speed=float(np.linalg.norm(env.env.data.qvel[3:6])),action_left=float(action[0]),action_right=float(action[1]))
   trace.append(row); rows.append(row)
   if terminated or truncated: break
  late=[r for r in trace if r['seconds']>=2] or trace
  summaries.append(dict(case=case['name'],controller=name,survived_seconds=trace[-1]['seconds'],late_mean_pitch=float(np.mean([r['pitch'] for r in late])),late_pitch_std=float(np.std([r['pitch'] for r in late])),late_mean_tilt=float(np.mean([r['tilt'] for r in late])),late_mean_angular_speed=float(np.mean([r['angular_speed'] for r in late])),tilt_band_fraction=float(np.mean([r['tilt']<=.1 for r in late])),speed_band_fraction=float(np.mean([r['angular_speed']<=.3 for r in late]))))
  env.close()
with (root/'diagnostic-traces.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
(root/'diagnostics.json').write_text(json.dumps(dict(summaries=summaries,episodes=12,cpu_seconds=time.process_time()-start,wall_seconds=time.monotonic()-wall),indent=2)+'\n')
print(json.dumps(summaries,indent=2))
