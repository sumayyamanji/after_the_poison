"""One-update FAA persistence experiments, with paired clean controls.

Controlled branch experiments condition on the intervention action, only when
that action has positive probability. They do NOT grant the attacker action
control. Warm-up uses natural action selection. Every transition is terminal.
"""
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import time
import numpy as np
from .learner import QLearner
from .mdp import build_mdp, build_targets
from .faa import FAA
from .persistence_theory import METRICS


def atomic_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def jobs(config):
    common = config['learner_defaults']
    for design in config['designs']:
        for rule, eta, budget, delta, init, branch in itertools.product(
                config['rules'], design['margins'], design['budgets'], design['delta_limits'],
                design['initializations'], design['branches']):
            spec = {**common, **design.get('learner_overrides', {}), 'rule': rule}
            condition = {'design': design['name'], 'mode': design['mode'], 'eta': eta,
                         'C': budget, 'Delta': delta, 'initialization': init,
                         'branch_request': branch, 'learner': spec}
            cid = digest(condition)
            # Fixed controlled UCB is deterministic. Warm-up from deterministic
            # rewards is also deterministic for UCB, but keep separate seeds if
            # future environments become random. Here there is no such randomness.
            seeds = 1 if rule == 'ucb' else config['seeds']
            for seed in range(seeds):
                yield {'id': f'{cid}-{seed:06d}', 'condition_id': cid,
                       'condition': condition, 'seed': seed}


def run_job(config, job):
    c = job['condition']; spec = c['learner']; seed = job['seed']
    rewards = np.array(config['rewards'], float)
    if rewards.shape != (2,) or not rewards[0] > rewards[1]:
        raise ValueError('This runner requires two terminal actions, rewards[0] > rewards[1]')
    env = build_mdp({'kind':'one_state', 'rewards':rewards.tolist()})
    init = c['initialization']
    if c['mode'] == 'controlled':
        learner = QLearner(1,2,spec,.9,rewards[None,:],np.array([init['counts']]))
    elif c['mode'] == 'warmup':
        learner = QLearner(1,2,spec,.9,np.full((1,2),float(init.get('q0',0.))))
        rng = np.random.default_rng(np.random.SeedSequence([seed,901]))
        for _ in range(init['steps']):
            a = learner.select(0,rng); learner.update(0,a,rewards[a],-1,True)
    else: raise ValueError('Unknown initialization mode')
    pre_q = learner.q[0].copy(); pre_counts = learner.counts[0].copy()
    probabilities = learner.probabilities(0)
    if c['branch_request'] == 'natural':
        rng = np.random.default_rng(np.random.SeedSequence([seed,227]))
        selected = learner.select(0,rng)
    else:
        if c['mode'] != 'controlled': raise ValueError('Warm-up runs must use natural selection')
        selected = {'demotion':0, 'promotion':1}[c['branch_request']]
        if probabilities[selected] == 0:
            return {**job, 'status':'skipped', 'reason':'Requested conditional action has zero selection probability'}
    branch = 'demotion' if selected == 0 else 'promotion'
    attacker = FAA(env,build_targets(env,'suboptimal_action'),
                   {'eta':c['eta'],'sign_convention':'corrected'},c['Delta'],c['C'])
    decision = attacker.decide(learner,0,selected,rewards[selected],-1,True)
    assert abs(decision.delta) <= c['Delta']+1e-10
    assert abs(decision.delta) <= c['C']+1e-10
    paired = []
    for arm in ['clean','faa']:
        victim = copy.deepcopy(learner)
        delta = decision.delta if arm == 'faa' else 0.
        alpha_at_intervention = victim.learning_rate(0,selected)
        victim.update(0,selected,rewards[selected],-1,True,delta)
        post_q = victim.q[0].copy(); post_counts = victim.counts[0].copy()
        times = {metric: None for metric in METRICS}; streak=0; wrong=0
        rng = np.random.default_rng(np.random.SeedSequence([seed,883]))
        for t in range(config['horizon']+1):
            error = float(np.max(np.abs(victim.q[0]-rewards)))
            if int(victim.q[0].argmax()) == 0 and times['greedy_recovery'] is None:
                times['greedy_recovery'] = t
            good = error <= config['q_tolerance']
            if good and times['q_recovery'] is None: times['q_recovery'] = t
            streak = streak+1 if good else 0
            if streak >= config['confirmation_window'] and times['q_confirmation'] is None:
                times['q_confirmation'] = t
            if t == config['horizon'] or all(x is not None for x in times.values()): break
            a = victim.select(0,rng)
            if a == selected and times['first_revisit'] is None: times['first_revisit'] = t+1
            wrong += int(a == 1)
            victim.update(0,a,rewards[a],-1,True)
        paired.append({'arm':arm, 'branch':branch, 'intervention_action':selected,
            'action_probability_before_intervention':float(probabilities[selected]),
            'conditional_action_experiment':c['branch_request'] != 'natural',
            'effective_attack':bool(delta != 0), 'delta':float(delta), 'spent':abs(float(delta)),
            'requested_delta':decision.requested if arm=='faa' else 0.,
            'clipped_by_delta':decision.capped_by_delta if arm=='faa' else False,
            'clipped_by_budget':decision.capped_by_budget if arm=='faa' else False,
            'alpha_at_intervention':alpha_at_intervention,
            'pre_q':pre_q.tolist(), 'pre_counts':pre_counts.tolist(),
            'pre_q_error':float(np.max(np.abs(pre_q-rewards))),
            'post_q':post_q.tolist(), 'post_counts':post_counts.tolist(),
            'post_q_error':float(np.max(np.abs(post_q-rewards))),
            'post_target_margin':float(post_q[1]-post_q[0]),
            'attained_target':bool(post_q[1] > post_q[0]),
            'times':times, 'censored':{m:times[m] is None for m in METRICS},
            'observed_clean_steps':t, 'wrong_action_steps_observed':wrong, 'final_q':victim.q[0].tolist(), 'final_q_error':error})
    return {**job, 'status':'complete', 'paired':paired}


def run_suite(config_path, out, resume=False, limit=None, dry_run=False):
    config = json.loads(Path(config_path).read_text())
    if config['seeds'] < 1 or config['horizon'] < 1 or config['q_tolerance'] <= 0 or config['confirmation_window'] < 1:
        raise ValueError('Invalid seed count, horizon or recovery settings')
    all_jobs = list(jobs(config)); out=Path(out)
    print(f'{len(all_jobs)} jobs, each with FAA and clean arms; horizon={config["horizon"]}',flush=True)
    if dry_run: return
    code_root = Path(__file__).parent
    code_hash = hashlib.sha256(b''.join((code_root/p).read_bytes() for p in
        ['persistence.py','learner.py','faa.py','mdp.py'])).hexdigest()
    manifest = {'config':config,'simulation_code_hash':code_hash,'python':platform.python_version(),
                'numpy':np.__version__,'job_count':len(all_jobs),'schema_version':1}
    if (out/'manifest.json').exists():
        old=json.loads((out/'manifest.json').read_text())
        if not resume: raise ValueError('Output exists; use --resume or choose a new directory')
        if old['config'] != config or old['simulation_code_hash'] != code_hash:
            raise ValueError('Config or simulation code changed: choose a new output directory')
    else:
        if out.exists() and any(out.iterdir()): raise ValueError('Nonempty output without manifest')
        atomic_json(out/'manifest.json',manifest)
    started=time.monotonic(); completed=0
    for job in all_jobs:
        path=out/'records'/f'{job["id"]}.json'
        if path.exists(): continue
        record=run_job(config,job); atomic_json(path,record)
        completed+=1
        if completed%10 == 0: print(f'Saved {completed} new jobs ({time.monotonic()-started:.1f}s)',flush=True)
        if limit is not None and completed >= limit: break
    print(f'Checkpointed {completed} new jobs to {out}; safe to resume.',flush=True)
