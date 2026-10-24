"""Bounded paired evaluation of the existing frozen checkpoint; never trains."""
import argparse
import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time

import torch
from stable_baselines3 import PPO
from robot_lab.robustness import Budget, protocol, summarize, trial

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'experiments/robustness-baseline'
SOURCES = ['benchmark_robustness.py', 'robot_lab/robustness.py', 'robot_lab/env.py', 'assets/robot.xml', 'tests/test_robustness.py', 'experiments/robustness-baseline/PROTOCOL.md']
MODEL = ROOT / 'experiments/balance-checkpoint-selection/policy.zip'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    return dict(protocol=protocol(), model_sha256=digest(MODEL),
                source_sha256={p: digest(ROOT / p) for p in SOURCES})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['development', 'holdout'], required=True)
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    output = DEST / f'{args.split}.json'
    if output.exists():
        parser.error('Refusing to overwrite an evaluated split; preserve results and budget')
    frozen = freeze()
    manifest = DEST / 'frozen-protocol.json'
    if args.split == 'development':
        if manifest.exists() and json.loads(manifest.read_text()) != frozen:
            parser.error('Protocol differs from existing freeze')
        manifest.write_text(json.dumps(frozen, indent=2) + '\n')
    elif not manifest.exists() or json.loads(manifest.read_text()) != frozen:
        parser.error('Holdout requires unchanged frozen implementation/protocol')
    if args.split == 'holdout' and not (DEST / 'development.json').exists():
        parser.error('Development must finish before holdout')
    ledger_path = DEST / 'budget.json'
    prior = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    budget = Budget(prior.get('episodes', 0), prior.get('cpu_seconds', 0))
    torch.set_num_threads(1)
    policy = PPO.load(MODEL, device='cpu')
    report = dict(split=args.split, freeze_sha256=digest(manifest), **frozen,
                  packages={p: version(p) for p in ['mujoco', 'gymnasium', 'stable-baselines3', 'torch', 'numpy']},
                  python=platform.python_version(), results=[], complete=False)
    started = time.monotonic()
    try:
        for case in protocol()['cases']:
            pairs = []
            report['results'].append(dict(scenario=case, trials=pairs))
            for seed in protocol()[f'{args.split}_seeds']:
                if time.monotonic() - started > 800:
                    raise RuntimeError('Wall time safety limit reached')
                pair = dict(seed=seed)
                for name, controller in [('ppo', policy), ('zero', None)]:
                    pair[name] = trial(controller, case, seed, budget)
                    ledger_path.write_text(json.dumps(dict(episodes=budget.episodes, cpu_seconds=budget.cpu_seconds), indent=2) + '\n')
                if pair['ppo']['reset_evidence']['after'] != pair['zero']['reset_evidence']['after']:
                    raise RuntimeError('Paired initial states/observations differ')
                pair['ppo_minus_zero'] = {key: float(pair['ppo'][key]) - float(pair['zero'][key])
                                          for key in ['seconds', 'success', 'recovered_without_later_fall', 'action_squared_integral']}
                pairs.append(pair)
            report['results'][-1]['summary'] = summarize(pairs)
            print(case['name'], json.dumps(report['results'][-1]['summary']), flush=True)
        all_pairs = [p for row in report['results'] for p in row['trials']]
        report['aggregate'] = summarize(all_pairs)
        report['by_kind'] = {kind: summarize([p for row in report['results'] if row['scenario']['kind'] == kind for p in row['trials']])
                             for kind in ['nominal', 'pitch', 'linear_velocity', 'angular_velocity', 'push']}
        report['complete'] = True
        if digest(MODEL) != frozen['model_sha256']:
            raise RuntimeError('Frozen checkpoint changed')
    finally:
        report['cumulative_evaluation_cpu_seconds'] = budget.cpu_seconds
        report['wall_seconds'] = time.monotonic() - started
        output.write_text(json.dumps(report, indent=2) + '\n')
        ledger_path.write_text(json.dumps(dict(episodes=budget.episodes, cpu_seconds=budget.cpu_seconds), indent=2) + '\n')
        with (DEST / f'{args.split}.csv').open('w') as stream:
            fields = ['scenario', 'kind', 'value', 'unit', 'seed', 'controller', 'seconds', 'success',
                      'terminated', 'truncated', 'recovery_window_seconds', 'recovered_without_later_fall',
                      'action_squared_integral', 'actual_impulse_Ns', 'initial_state_sha256']
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in report['results']:
                for pair in row['trials']:
                    for controller in ('ppo', 'zero'):
                        trial_row = pair[controller]
                        writer.writerow(dict(scenario=row['scenario']['name'], kind=row['scenario']['kind'],
                                             value=row['scenario']['value'], unit=row['scenario']['unit'],
                                             controller=controller, **{k: trial_row[k] for k in fields[4:] if k != 'controller'}))


if __name__ == '__main__':
    main()
