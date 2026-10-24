"""One bounded CPU candidate experiment; immutable baseline evaluation is reused."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import resource
import time

import numpy as np
import torch
from importlib.metadata import version
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from robot_lab.robustness import Budget, protocol, trial, summarize
from robot_lab.settling import SettlingEnv, VALIDATION_SEEDS, CHECKPOINT_STEPS, selection_score

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'experiments/settling-candidate'
ORIGINAL = ROOT / 'experiments/balance-checkpoint-selection/policy.zip'
SOURCES = ['improve_settling.py', 'robot_lab/settling.py', 'tests/test_settling.py', 'robot_lab/robustness.py', 'robot_lab/env.py', 'assets/robot.xml', 'train.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')


def freeze():
    return dict(original_sha256=sha(ORIGINAL), sources={p: sha(ROOT / p) for p in SOURCES},
                protocol_sha256=sha(OUT / 'PROTOCOL.md'), benchmark_protocol=protocol(),
                packages={p: version(p) for p in ['mujoco','gymnasium','stable-baselines3','torch','numpy']}, python=platform.python_version())


class MilestoneBudget:
    def __init__(self):
        self.path = OUT / 'budget.json'
        self.state = json.loads(self.path.read_text())
        self.started_cpu = time.process_time()
        self.prior_cpu = self.state['cpu_seconds']
        # Never permit consumption of the full user budget; keep overhead margin.
        resource.setrlimit(resource.RLIMIT_CPU, (int(max(1, 550-self.prior_cpu)), int(max(2, 555-self.prior_cpu))))

    def check(self):
        if time.time() - self.state['wall_start_unix'] > 850 or self.cpu() > 550:
            raise RuntimeError('Milestone time budget reached')

    def cpu(self):
        return self.prior_cpu + time.process_time() - self.started_cpu

    def save(self):
        self.state['cpu_seconds'] = self.cpu()
        self.state['wall_elapsed_seconds'] = time.time() - self.state['wall_start_unix']
        write('budget.json',self.state)

    def reserve(self):
        self.check()
        if self.state['evaluation_episodes'] >= 2400:
            raise RuntimeError('Evaluation episode budget reached')
        self.state['evaluation_episodes'] += 1
        self.save()


def evaluate(models, seeds, budget):
    rows=[]
    for case in protocol()['cases']:
        pairs=[]
        rows.append(dict(scenario=case, trials=pairs))
        for seed in seeds:
            pair=dict(seed=seed)
            for name, model in models.items():
                pair[name]=trial(model,case,seed,budget)
            states=[p['reset_evidence']['after'] for name,p in pair.items() if name!='seed']
            if any(s!=states[0] for s in states[1:]):
                raise RuntimeError('Unequal paired initial observations/states')
            pairs.append(pair)
    # summarize() names first policy ppo and comparator zero; keep raw controller names.
    comparisons={}
    for comparator in [n for n in models if n!='candidate']:
        pairs=[dict(seed=p['seed'],ppo=p['candidate'],zero=p[comparator]) for r in rows for p in r['trials']]
        comparisons[comparator]=summarize(pairs)
    return dict(seeds=list(seeds), results=rows, comparisons=comparisons)


def save_report(name, report):
    write(name+'.json',report)
    keys=['seed','seconds','success','terminated','truncated','recovery_window_seconds','recovered_without_later_fall','action_squared_integral','actual_impulse_Ns','initial_state_sha256']
    with (OUT/(name+'.csv')).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['case','controller']+keys,lineterminator='\n');writer.writeheader()
        for row in report['results']:
            for pair in row['trials']:
                for controller,t in pair.items():
                    if controller!='seed':
                        writer.writerow(dict(case=row['scenario']['name'],controller=controller,**{k:t[k] for k in keys}))


class Selection(BaseCallback):
    def __init__(self, budget, original):
        super().__init__(); self.budget=budget; self.original=original
        self.history=[]; self.best=None; self.selected=None; self.training_cpu=0.
        self.validation_cpu=0.; self.training_start=None

    def _on_step(self):
        self.budget.check()
        if time.process_time()-self.training_start-self.validation_cpu > 270:
            raise RuntimeError('Training CPU guard reached')
        return True

    def consider(self):
        if self.num_timesteps not in CHECKPOINT_STEPS or any(h['steps']==self.num_timesteps for h in self.history):
            return
        start=time.process_time()
        report=evaluate({'candidate':self.model,'original':self.original},VALIDATION_SEEDS,self.budget)
        score=selection_score(report['comparisons']['original'], self.reference_rate)
        if self.best is None or score>self.best:
            self.best=score;self.selected=self.num_timesteps
            self.model.save(OUT/'candidate.zip')
        save_report(f'validation-{self.num_timesteps}', report)
        self.history.append(dict(steps=self.num_timesteps, score=score, selected_steps=self.selected))
        write('selection.json',dict(history=self.history,selected_steps=self.selected))
        self.validation_cpu+=time.process_time()-start

    def _on_rollout_start(self):
        self.consider()  # Prior rollout PPO update has completed.

    def _on_training_end(self):
        self.consider()


def acceptance(report, nominal):
    s=report['comparisons']['original']; p,o=s['ppo'],s['zero']
    return (p['recoveries']>o['recoveries'] and
            p['successes']/p['trials']>=o['successes']/o['trials']-.05-1e-12 and nominal==10)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['train','development','holdout'])
    args=parser.parse_args();torch.set_num_threads(1)
    frozen=json.loads((OUT/'frozen-choices.json').read_text())
    if freeze()!=frozen: raise RuntimeError('Frozen choices/source changed')
    budget=MilestoneBudget(); budget.check()
    original=PPO.load(ORIGINAL,device='cpu')
    try:
        if args.phase=='train':
            marker=OUT/'training-attempt.json'
            with marker.open('x') as f: json.dump(dict(status='started',time=time.time(),single_attempt=True),f)
            env=SettlingEnv()
            model=PPO.load(ORIGINAL,env=env,device='cpu',seed=71)
            model.learning_rate=1e-4;model.lr_schedule=lambda _:1e-4
            model.ent_coef=0.;model.n_epochs=10;model.tensorboard_log=None
            callback=Selection(budget,original)
            # Original validation rate is fixed from development baseline only.
            baseline=json.loads((ROOT/'experiments/robustness-baseline/development.json').read_text())
            vals=[p['ppo'] for r in baseline['results'] for p in r['trials'] if p['seed'] in VALIDATION_SEEDS]
            callback.reference_rate=sum(t['success'] for t in vals)/len(vals)
            callback.training_start=time.process_time()
            resource.setrlimit(resource.RLIMIT_CPU,(min(290,resource.getrlimit(resource.RLIMIT_CPU)[0]),min(295,resource.getrlimit(resource.RLIMIT_CPU)[1])))
            try:
                model.learn(total_timesteps=20480,callback=callback,reset_num_timesteps=True)
                model.save(OUT/'candidate-final.zip')
                # Load the selected artifact as part of this one real run, not another smoke run.
                loaded=PPO.load(OUT/'candidate.zip',device='cpu')
                assert loaded.num_timesteps==callback.selected
                write('training-attempt.json',dict(status='complete',actual_steps=model.num_timesteps,
                    training_cpu_seconds=time.process_time()-callback.training_start-callback.validation_cpu,
                    validation_cpu_seconds=callback.validation_cpu,selected_steps=callback.selected,
                    candidate_sha256=sha(OUT/'candidate.zip'),single_attempt=True))
            finally: env.close()
        else:
            candidate=PPO.load(OUT/'candidate.zip',device='cpu')
            if args.phase=='holdout':
                gate=json.loads((OUT/'development-gate.json').read_text())
                if not gate['accepted'] or gate['candidate_sha256']!=sha(OUT/'candidate.zip'):
                    raise RuntimeError('Development gate failed or candidate changed')
                seeds=list(range(6000,6020))
            else: seeds=list(range(4000,4010))
            target=OUT/(args.phase+'.json')
            if target.exists(): raise RuntimeError('Refusing duplicate split evaluation')
            report=evaluate({'candidate':candidate,'original':original,'zero':None},seeds,budget)
            save_report(args.phase,report)
            if args.phase=='development':
                # Unchanged original nominal protocol, candidate must also retain 10/10.
                cases=[protocol()['cases'][0]]
                nominal=[trial(candidate,cases[0],seed,budget) for seed in range(1000,1010)]
                write('candidate-nominal.json',nominal)
                count=sum(t['success'] for t in nominal)
                write('development-gate.json',dict(accepted=acceptance(report,count),nominal_successes=count,
                    candidate_sha256=sha(OUT/'candidate.zip'),choices_sha256=sha(OUT/'frozen-choices.json'),
                    holdout='6000-6019 authorized only if accepted; choices now immutable'))
    finally: budget.save()


if __name__=='__main__': main()
