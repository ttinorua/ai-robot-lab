"""Isolated disturbance wrapper and paired frozen-policy evaluation."""
import hashlib
import time

import mujoco
import numpy as np

from robot_lab import BalanceEnv


def protocol():
    cases = [{'name': 'nominal', 'kind': 'nominal', 'value': 0.0, 'unit': 'none'}]
    for kind, values, unit in [('pitch', (0.08, 0.16), 'rad'),
                               ('linear_velocity', (0.2, 0.5), 'm/s'),
                               ('angular_velocity', (0.5, 1.0), 'rad/s'),
                               ('push', (0.5, 1.5), 'N s')]:
        for strength, magnitude in zip(('small', 'medium'), values):
            for sign in (-1, 1):
                cases.append(dict(name=f'{kind}_{strength}_{sign:+d}', kind=kind,
                                  strength=strength, value=sign * magnitude, unit=unit))
    return dict(version='robustness-baseline-v1', cases=cases,
                axes='world x forward, y lateral, z up; pitch about +y',
                reset='same seeded nominal reset; replace root pitch or add root velocity',
                push=dict(start_step=50, end_step_exclusive=55, start_seconds=1.0,
                          duration_seconds=0.1, substep_seconds=0.01,
                          application='constant world-x force at torso COM; zero torque',
                          force_newtons='signed impulse / 0.1; +/-5 N or +/-15 N'),
                recovery=dict(max_tilt_rad=0.10, max_angular_speed_rad_s=0.3,
                              sustained_seconds=0.5,
                              start='reset disturbances: t=0; pushes: end of force at t=1.1',
                              definition='first 0.5 s continuous qualifying window; latency to window end; falls fail'),
                success='10 s horizon reached without fall, including last step',
                development_seeds=list(range(4000, 4010)), holdout_seeds=list(range(5000, 5020)))


class RobustnessEnv:
    """Delegate all integration, rewards and fall thresholds to unchanged BalanceEnv."""
    def __init__(self, case):
        self.env = BalanceEnv()
        self.case = case
        self.push_evidence = []

    def reset(self, seed):
        self.env.reset(seed=seed)
        data = self.env.data
        before = self.state()
        kind, value = self.case['kind'], self.case['value']
        if kind == 'pitch':
            data.qpos[3:7] = [np.cos(value / 2), 0, np.sin(value / 2), 0]
        elif kind == 'linear_velocity':
            data.qvel[0] += value
        elif kind == 'angular_velocity':
            data.qvel[4] += value
        elif kind not in ('nominal', 'push'):
            raise ValueError(f'Unknown disturbance {kind}')
        data.xfrc_applied[:] = 0
        mujoco.mj_forward(self.env.model, data)
        self.push_evidence = []
        self.initial_evidence = {'before': before, 'after': self.state()}
        return self.env._obs()

    def state(self):
        data = self.env.data
        return {'qpos': data.qpos.tolist(), 'qvel': data.qvel.tolist(),
                'observation': self.env._obs().tolist()}

    def step(self, action):
        env = self.env
        active = self.case['kind'] == 'push' and 50 <= env.steps < 55
        env.data.xfrc_applied[:] = 0
        evidence = None
        if active:
            force = self.case['value'] / 0.1
            env.data.xfrc_applied[env.model.body('torso').id, 0] = force
            evidence = {'step': env.steps, 'start_seconds': float(env.data.time),
                        'force_world_N': [force, 0., 0.], 'substeps': 2,
                        'integrated_impulse_Ns': force * 2 * env.model.opt.timestep,
                        'before': self.state()}
        try:
            result = env.step(action)  # Force persists through both 0.01 s MuJoCo substeps.
            if evidence is not None:
                evidence.update(end_seconds=float(env.data.time), after=self.state())
                self.push_evidence.append(evidence)
            return result
        finally:
            env.data.xfrc_applied[:] = 0

    def close(self):
        self.env.close()


def success(terminated, truncated):
    return bool(truncated and not terminated)


class Budget:
    """Shared across development/holdout. Caller persists counters after each trial."""
    def __init__(self, episodes=0, cpu_seconds=0.):
        self.episodes = episodes
        self.previous_cpu = cpu_seconds
        self.started = time.process_time()

    @property
    def cpu_seconds(self):
        return self.previous_cpu + time.process_time() - self.started

    def reserve(self):
        if self.episodes >= 1450 or self.cpu_seconds >= 840:
            raise RuntimeError('Evaluation budget exhausted (reserve left for tests)')
        self.episodes += 1


class RecoveryTracker:
    def __init__(self, onset):
        self.onset = onset
        self.streak = 0
        self.latency = None

    def update(self, step, tilt, angular_speed, fallen):
        criteria = protocol()['recovery']
        eligible = step * .02 >= self.onset - 1e-9
        if eligible and not fallen and tilt <= criteria['max_tilt_rad'] and angular_speed <= criteria['max_angular_speed_rad_s']:
            self.streak += 1
        else:
            self.streak = 0
        if self.streak >= 25 and self.latency is None:
            self.latency = round((step + 1) * .02 - self.onset, 8)


def trial(policy, case, seed, budget):
    budget.reserve()
    wrapper = RobustnessEnv(case)
    try:
        obs = wrapper.reset(seed)
        evidence = wrapper.initial_evidence
        state_hash = hashlib.sha256(np.array(evidence['after']['qpos'] + evidence['after']['qvel'], dtype=np.float64).tobytes()).hexdigest()
        effort = 0.
        onset = 1.1 if case['kind'] == 'push' else 0.
        recovery = RecoveryTracker(onset)
        peak_tilt = 0.
        for step in range(500):
            action = np.zeros(2) if policy is None else policy.predict(obs, deterministic=True)[0]
            obs, reward, terminated, truncated, info = wrapper.step(action)
            if not np.isfinite(obs).all() or not np.isfinite(reward):
                raise RuntimeError(f'Nonfinite simulation: {case["name"]}, seed {seed}')
            effort += float(np.sum(np.square(action))) * 0.02
            # Refresh derived kinematics at the integrated state, without integrating again.
            mujoco.mj_forward(wrapper.env.model, wrapper.env.data)
            tilt = float(np.arccos(np.clip(wrapper.env.data.body('torso').xmat[8], -1, 1)))
            speed = float(np.linalg.norm(wrapper.env.data.qvel[3:6]))
            peak_tilt = max(peak_tilt, tilt)
            recovery.update(step, tilt, speed, terminated)
            if terminated or truncated:
                break
        else:
            raise RuntimeError('Environment did not stop at horizon')
        return dict(seed=seed, perturbation=case, initial_state_sha256=state_hash,
                    reset_evidence=evidence, push_evidence=wrapper.push_evidence,
                    actual_impulse_Ns=sum(e['integrated_impulse_Ns'] for e in wrapper.push_evidence),
                    seconds=info['survived_seconds'], success=success(terminated, truncated),
                    terminated=bool(terminated), truncated=bool(truncated),
                    recovery_window_seconds=recovery.latency,
                    recovered_without_later_fall=bool(recovery.latency is not None and not terminated),
                    action_squared_integral=effort, peak_torso_tilt_rad=peak_tilt)
    finally:
        wrapper.close()


def summarize(pairs):
    result = {}
    for controller in ('ppo', 'zero'):
        rows = [p[controller] for p in pairs]
        times = [r['recovery_window_seconds'] for r in rows if r['recovered_without_later_fall']]
        result[controller] = dict(successes=sum(r['success'] for r in rows), trials=len(rows),
                                  mean_seconds=float(np.mean([r['seconds'] for r in rows])),
                                  recoveries=sum(r['recovered_without_later_fall'] for r in rows),
                                  mean_recovery_seconds_conditional=float(np.mean(times)) if times else None)
    # Resample paired seeds, retaining every scenario within a seed as a cluster.
    seeds = sorted(set(p['seed'] for p in pairs))
    metrics = ('seconds', 'success', 'recovered_without_later_fall')
    rng = np.random.default_rng(61982)
    indices = rng.integers(0, len(seeds), (4000, len(seeds)))
    for metric in metrics:
        deltas = np.array([np.mean([float(p['ppo'][metric]) - float(p['zero'][metric]) for p in pairs if p['seed'] == seed]) for seed in seeds])
        interval = np.quantile(deltas[indices].mean(axis=1), [0.025, 0.975]).tolist()
        result[f'paired_{metric}'] = dict(mean=float(deltas.mean()), bootstrap_95_percent=interval)
    result['ppo_only_successes'] = sum(p['ppo']['success'] and not p['zero']['success'] for p in pairs)
    result['zero_only_successes'] = sum(p['zero']['success'] and not p['ppo']['success'] for p in pairs)
    return result
