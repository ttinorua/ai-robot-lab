"""Predeclared finite search, selection and paired evaluation; never trains."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import resource
import sys

import numpy as np
import torch
from stable_baselines3 import PPO
from controller import Feedback,gain_grid
from engine import ROOT,Budget,rollout,totals,rank
from robot_lab.robustness import protocol,summarize

SOURCE=[ROOT/'controller.py',ROOT/'engine.py',ROOT/'run.py',ROOT/'PROTOCOL.md',Path('tests/test_upright_feedback.py')]


def hash_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):(ROOT/name).write_text(json.dumps(data,indent=2)+'\n')
def frozen():return dict(sources={str(p):hash_file(p) for p in SOURCE},parameters=gain_grid(),benchmark=protocol())


def choose(records):
    # Stable earliest tie; only tuning rows are passed here.
    return sorted(range(len(records)),key=lambda i:rank(records[i]['summary']),reverse=True)[:4]


def gate(report,nominal):
    s=report['summaries'];c=s['candidate'];n=c['trials']
    return bool(nominal==10 and c['survivals']/n>=.90 and c['recoveries']/n>=.80 and
                c['recoveries']>s['original']['recoveries'] and c['recoveries']>s['zero']['recoveries'])


def paired(models,seeds,budget):
    rows=[]
    for case in protocol()['cases']:
        pairs=[];rows.append(dict(scenario=case,trials=pairs))
        for seed in seeds:
            pair=dict(seed=seed)
            for name,policy in models.items():pair[name]=rollout(policy,case,seed,budget,trace=(name=='candidate' and seed==seeds[0]))
            states=[p['reset_evidence']['after'] for k,p in pair.items() if k!='seed']
            assert all(s==states[0] for s in states)
            pairs.append(pair)
    summary={k:totals([p[k] for r in rows for p in r['trials']]) for k in models}
    comparisons={k:summarize([dict(seed=p['seed'],ppo=p['candidate'],zero=p[k]) for r in rows for p in r['trials']]) for k in models if k!='candidate'}
    return dict(seeds=seeds,results=rows,summaries=summary,comparisons=comparisons)


def flat(name,report):
    fields=['case','seed','controller','seconds','success','recovered_without_later_fall','recovery_window_seconds','action_squared_integral','saturation_fraction','mean_tilt_rad','peak_torso_tilt_rad','nonfoot_contact_fraction','final_in_band','actual_impulse_Ns','initial_state_sha256']
    with (ROOT/(name+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for row in report['results']:
            for pair in row['trials']:
                for k,t in pair.items():
                    if k!='seed':w.writerow(dict(case=row['scenario']['name'],controller=k,**{key:t[key] for key in fields[1:] if key!='controller'}))


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['search','development','holdout']);args=p.parse_args()
    torch.set_num_threads(1);resource.setrlimit(resource.RLIMIT_CPU,(300,305));budget=Budget();budget.check()
    if frozen()!=json.loads((ROOT/'frozen-search.json').read_text()):raise RuntimeError('Frozen search changed')
    output=ROOT/(args.phase+'.json')
    if output.exists():raise RuntimeError('Phase already evaluated; never overwrite')
    report={}
    try:
        if args.phase=='search':
            tuning_names=['nominal','pitch_medium_-1','pitch_medium_+1','linear_velocity_medium_-1','angular_velocity_medium_+1','push_medium_-1','push_medium_+1']
            cases=[c for c in protocol()['cases'] if c['name'] in tuning_names]
            records=[];report=dict(tuning=records,selection=[])
            for index,params in enumerate(gain_grid()):
                trials=[];entry=dict(index=index,parameters=params,trials=trials,status='started');records.append(entry)
                for case in cases:
                    for seed in (4000,4003):trials.append(rollout(Feedback(params),case,seed,budget))
                summary=totals(trials);entry.update(summary=summary,status='complete')
                write('search-progress.json',report);print(index,params['name'],summary,flush=True)
            shortlist=choose(records)
            for index in shortlist:
                trials=[rollout(Feedback(gain_grid()[index]),case,seed,budget) for case in protocol()['cases'] for seed in (4008,4009)]
                report['selection'].append(dict(index=index,parameters=gain_grid()[index],trials=trials,summary=totals(trials)))
            winner=max(report['selection'],key=lambda r:rank(r['summary']))
            selected=dict(index=winner['index'],parameters=winner['parameters'],shortlist=shortlist,
                          selection_seeds=[4008,4009],tuning_seeds=[4000,4003],frozen_search_sha256=hash_file(ROOT/'frozen-search.json'))
            write('selected.json',selected);print('SELECTED',selected,flush=True)
        else:
            selected=json.loads((ROOT/'selected.json').read_text())
            if args.phase=='holdout':
                g=json.loads((ROOT/'development-gate.json').read_text())
                if not g['accepted'] or g['selected_sha256']!=hash_file(ROOT/'selected.json'):raise RuntimeError('Holdout gate failed')
                if not json.loads((ROOT/'seed-audit.json').read_text())['unused_6000_6019']:raise RuntimeError('Holdout previously used')
                seeds=list(range(6000,6020))
                # Reserve once before evaluations; a failed final run also retires these seeds.
                with (ROOT/'holdout-retired.json').open('x') as f:json.dump(dict(seeds=seeds,retired=True),f)
            else:seeds=list(range(4000,4010))
            models=dict(candidate=Feedback(selected['parameters']),original=PPO.load('experiments/balance-checkpoint-selection/policy.zip',device='cpu'),zero=None)
            report=paired(models,seeds,budget);flat(args.phase,report)
            if args.phase=='development':
                nominal=[rollout(models['candidate'],protocol()['cases'][0],seed,budget,True) for seed in range(1000,1010)]
                write('candidate-nominal.json',nominal)
                write('development-gate.json',dict(accepted=gate(report,sum(t['success'] for t in nominal)),
                    nominal_successes=sum(t['success'] for t in nominal),selected_sha256=hash_file(ROOT/'selected.json'),
                    frozen_search_sha256=hash_file(ROOT/'frozen-search.json'),summaries=report['summaries']))
            print(json.dumps(report['summaries']),flush=True)
    except Exception as exc:
        report['error']=repr(exc);raise
    finally:write(args.phase+'.json',report);budget.save()


if __name__=='__main__':main()
