"""One bounded residual PPO run with immutable source/choice and model gates."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import resource
import time
from importlib.metadata import version

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from robot_lab.robustness import protocol,summarize
from residual import ROOT,BASE_ROOT,PARAMETERS,feedback,engine,DisturbanceEnv,ResidualActionWrapper,ResidualController,new_model,CHECKPOINT_STEPS,VALIDATION_SEEDS,VALIDATION_NAMES

SOURCES=[ROOT/'residual.py',ROOT/'run.py',ROOT/'PROTOCOL.md',ROOT/'SOURCES.md',Path('tests/test_residual_feedback.py')]
PROTECTED=[BASE_ROOT/'controller.py',BASE_ROOT/'engine.py',BASE_ROOT/'selected.json',BASE_ROOT/'development.json.gz',Path('robot_lab/env.py'),Path('assets/robot.xml'),Path('train.py'),Path('robot_lab/robustness.py'),Path('experiments/balance-checkpoint-selection/policy.zip')]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):(ROOT/name).write_text(json.dumps(data,indent=2)+'\n')
def freeze():return dict(sources={str(p):sha(p) for p in SOURCES},protected={str(p):sha(p) for p in PROTECTED},packages={p:version(p) for p in ['stable-baselines3','torch','mujoco','gymnasium','numpy']},python=platform.python_version(),bound_evidence_sha256=sha(ROOT/'torque-bound-evidence.json'))


class Budget:
    def __init__(self):
        self.state=json.loads((ROOT/'budget.json').read_text());self.start=time.process_time();self.prior=self.state['cpu_seconds']
        remaining=int(max(1,550-self.prior));resource.setrlimit(resource.RLIMIT_CPU,(remaining,remaining+2))
    def check(self):
        if self.prior+time.process_time()-self.start>550 or time.time()-self.state['wall_start_unix']>1140:raise RuntimeError('Milestone CPU/wall guard')
    def reserve(self):
        self.check()
        # 250 additional controller-test/reset episodes reserved for the single public CI.
        if self.state['evaluation_episodes']>=2250:raise RuntimeError('Evaluation episode guard')
        self.state['evaluation_episodes']+=1;self.save()
    def save(self):write('budget.json',dict(self.state,cpu_seconds=self.prior+time.process_time()-self.start,wall_seconds=time.time()-self.state['wall_start_unix']))


def evaluate(models,seeds,budget,cases=None):
    rows=[]
    for case in cases or protocol()['cases']:
        pairs=[];rows.append(dict(scenario=case,trials=pairs))
        for seed in seeds:
            pair=dict(seed=seed)
            for name,policy in models.items():
                if isinstance(policy,ResidualController):policy.reset_stats()
                pair[name]=engine.rollout(policy,case,seed,budget)
                if isinstance(policy,ResidualController):pair[name].update(policy.stats())
            states=[r['reset_evidence']['after'] for n,r in pair.items() if n!='seed']
            if any(s!=states[0] for s in states):raise RuntimeError('Paired state/observation mismatch')
            pairs.append(pair)
    summaries={name:engine.totals([p[name] for row in rows for p in row['trials']]) for name in models}
    comparisons={name:summarize([dict(seed=p['seed'],ppo=p['candidate'],zero=p[name]) for row in rows for p in row['trials']]) for name in models if name!='candidate'}
    return dict(seeds=list(seeds),results=rows,summaries=summaries,comparisons=comparisons)


def save_report(name,report):
    write(name+'.json',report)
    fields=['case','controller','seed','seconds','success','recovered_without_later_fall','recovery_window_seconds','final_in_band','action_squared_integral','saturation_fraction','nonfoot_contact_fraction','mean_tilt_rad','actual_impulse_Ns','initial_state_sha256','residual_clip_steps','total_clip_steps','residual_effort_Nm_squared_seconds']
    with (ROOT/(name+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for row in report['results']:
            for pair in row['trials']:
                for name,t in pair.items():
                    if name!='seed' and isinstance(t,dict):w.writerow(dict(case=row['scenario']['name'],controller=name,**{k:t.get(k) for k in fields[2:]}))


def score(candidate,base):
    eligible=candidate['survivals']>=base['survivals']
    return (eligible,candidate['recoveries'] if eligible else 0,candidate['survivals'],candidate['mean_seconds'])


def gate(report,nominal):
    c=report['summaries']['candidate'];b=report['summaries']['base']
    return bool(nominal==10 and c['recoveries']>b['recoveries'] and c['survivals']>=b['survivals'])


class Checkpoints(BaseCallback):
    def __init__(self,budget):
        super().__init__();self.budget=budget;self.history=[];self.best=None;self.selected=None
        self.validation_cpu=0.;self.started=None;self.raw_residual_clips=0
    def _on_step(self):
        self.budget.check()
        self.raw_residual_clips+=int((abs(self.locals['actions'])>1).any())
        if time.process_time()-self.started-self.validation_cpu>270:raise RuntimeError('Training CPU guard')
        return True
    def consider(self):
        if self.num_timesteps not in CHECKPOINT_STEPS or any(r['steps']==self.num_timesteps for r in self.history):return
        start=time.process_time();cases=[c for c in protocol()['cases'] if c['name'] in VALIDATION_NAMES]
        report=evaluate(dict(candidate=ResidualController(self.model)),VALIDATION_SEEDS,self.budget,cases)
        report['base_validation']=self.base_validation
        report['base_reference_archive_sha256']=sha(BASE_ROOT/'development.json.gz')
        for row in report['results']:
            for pair in row['trials']:
                ref=self.base_rows[(row['scenario']['name'],pair['seed'])]
                if pair['candidate']['initial_state_sha256']!=ref['initial_state_sha256']:raise RuntimeError('Validation pairing differs from frozen base')
                pair['frozen_base_initial_state_sha256']=ref['initial_state_sha256']
        choice=score(report['summaries']['candidate'],self.base_validation)
        path=ROOT/f'checkpoint-{self.num_timesteps}.zip';self.model.save(path)
        if self.best is None or choice>self.best:
            self.best=choice;self.selected=self.num_timesteps;self.model.save(ROOT/'candidate.zip')
        save_report(f'validation-{self.num_timesteps}',report)
        self.history.append(dict(steps=self.num_timesteps,score=choice,selected_steps=self.selected,checkpoint_sha256=sha(path)))
        write('selection.json',dict(history=self.history,selected_steps=self.selected))
        self.validation_cpu+=time.process_time()-start
    def _on_rollout_start(self):self.consider()
    def _on_training_end(self):self.consider()


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['train','development','holdout']);args=p.parse_args();torch.set_num_threads(1)
    current=freeze();expected=json.loads((ROOT/'frozen-choices.json').read_text())
    if current!=expected:
        fix=json.loads((ROOT/'reporting-fix.json').read_text());key=str(ROOT/'run.py')
        if current['sources'][key]!=fix['corrected_run_sha256'] or expected['sources'][key]!=fix['frozen_run_sha256']:raise RuntimeError('Unrecognized reporting fix')
        current['sources'][key]=expected['sources'][key]
        if current!=expected or args.phase=='train':raise RuntimeError('Frozen choices changed or training retry forbidden')
    budget=Budget();budget.check()
    try:
        if args.phase=='train':
            with (ROOT/'training-attempt.json').open('x') as f:json.dump(dict(status='started',single_attempt=True),f)
            env=ResidualActionWrapper(DisturbanceEnv(training=True));model=new_model(env);model.save(ROOT/'initialized-residual.zip')
            callback=Checkpoints(budget)
            previous=json.loads((BASE_ROOT/'development.json').read_text())
            rows=[p['candidate'] for row in previous['results'] if row['scenario']['name'] in VALIDATION_NAMES for p in row['trials'] if p['seed'] in VALIDATION_SEEDS]
            callback.base_validation=engine.totals(rows)
            callback.base_rows={(row['scenario']['name'],p['seed']):p['candidate'] for row in previous['results'] for p in row['trials']}
            callback.started=time.process_time()
            resource.setrlimit(resource.RLIMIT_CPU,(290,295))
            try:
                model.learn(total_timesteps=32768,callback=callback)
                model.save(ROOT/'final-residual.zip')
                loaded=PPO.load(ROOT/'candidate.zip',device='cpu');assert loaded.num_timesteps==callback.selected
                write('training-attempt.json',dict(status='complete',single_attempt=True,actual_new_steps=model.num_timesteps,
                    selected_steps=callback.selected,candidate_sha256=sha(ROOT/'candidate.zip'),
                    training_cpu_seconds=time.process_time()-callback.started-callback.validation_cpu,validation_cpu_seconds=callback.validation_cpu,
                    raw_residual_clip_steps=callback.raw_residual_clips,wrapper_residual_clip_steps=env.residual_clip_steps,
                    total_clip_steps=env.total_clip_steps,training_resets=len(env.env.seed_log),actual_training_seeds=sorted(set(env.env.seed_log))))
            finally:env.close()
        else:
            if (ROOT/(args.phase+'.json')).exists():raise RuntimeError('Refusing evaluated phase overwrite')
            candidate=PPO.load(ROOT/'candidate.zip',device='cpu')
            if args.phase=='holdout':
                if json.loads((ROOT/'training-attempt.json').read_text())['status']!='complete':raise RuntimeError('Interrupted training protocol: no new holdout')
                g=json.loads((ROOT/'development-gate.json').read_text())
                if not g['accepted'] or sha(ROOT/'candidate.zip')!=g['candidate_sha256']:raise RuntimeError('No holdout without development gain')
                if not json.loads((ROOT/'seed-audit.json').read_text())['unused_7000_7019']:raise RuntimeError('Holdout used')
                seeds=list(range(7000,7020))
                with (ROOT/'holdout-retired.json').open('x') as f:json.dump(dict(seeds=seeds,retired=True),f)
            else:seeds=list(range(4000,4010))
            models=dict(candidate=ResidualController(candidate),base=feedback.Feedback(PARAMETERS),original=PPO.load('experiments/balance-checkpoint-selection/policy.zip',device='cpu'),zero=None)
            report=evaluate(models,seeds,budget);save_report(args.phase,report)
            if args.phase=='development':
                nominal=[engine.rollout(models['candidate'],protocol()['cases'][0],seed,budget) for seed in range(1000,1010)]
                write('candidate-nominal.json',nominal);count=sum(t['success'] for t in nominal)
                write('development-gate.json',dict(accepted=gate(report,count),candidate_sha256=sha(ROOT/'candidate.zip'),nominal_successes=count,
                    choices_sha256=sha(ROOT/'frozen-choices.json'),summaries=report['summaries']))
            print(json.dumps(report['summaries']),flush=True)
    finally:budget.save()


if __name__=='__main__':main()
