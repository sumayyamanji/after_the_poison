"""Paired, fixed-horizon multi-state FAA protocol. See MULTISTEP_PROTOCOL.md.

Simulation records are atomic compressed JSON, one complete paired job per file.
No analysis code is included in the simulation resume fingerprint.
"""
import copy
import gzip
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
from .faa import FAA, AttackDecision, margins

SCHEMA = 1
EVENTS = ('target_loss', 'greedy_recovery', 'q_recovery',
          'greedy_confirmation', 'q_confirmation')


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    raw = json.dumps(data, allow_nan=False, separators=(',', ':')).encode()
    if path.suffix == '.gz':
        raw = gzip.compress(raw, mtime=0)
    with temporary.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_json(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def source_hash():
    root = Path(__file__).resolve().parent
    result = {}
    for name in ('multistep.py', 'learner.py', 'mdp.py', 'faa.py'):
        result[name] = hashlib.sha256((root/name).read_bytes()).hexdigest()
    return result


def validate(config):
    for key in ('attack_steps', 'post_steps', 'confirmation', 'trace_every', 'seeds'):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if not 0 <= config['gamma'] < 1 or config['q_tolerance'] <= 0:
        raise ValueError('Invalid discount or accuracy tolerance')
    if not config['designs'] or not config['rules']:
        raise ValueError('Supply designs and action-selection rules')
    if len({x['name'] for x in config['designs']}) != len(config['designs']):
        raise ValueError('Design names must be unique')
    for key in ('budgets', 'delta_limits', 'margins', 'sign_conventions'):
        if not config[key] or len(set(config[key])) != len(config[key]):
            raise ValueError(f'{key} must be a nonempty unique list')
    for key in ('budgets', 'delta_limits'):
        if any(not np.isfinite(x) or x < 0 for x in config[key]):
            raise ValueError(f'{key} must be finite and nonnegative')
    if len(set(config['rules'])) != len(config['rules']):
        raise ValueError('Repeated rule')
    for design in config['designs']:
        env = build_mdp(design['environment'])
        target = build_targets(env, design['targets'])
        if target.all():
            raise ValueError('At least one constrained target is required')
        init = design['initialization']
        if init['mode'] not in ('warmup', 'controlled'):
            raise ValueError('Unknown initialization mode')
        if init['mode'] == 'warmup' and (type(init['steps']) is not int or init['steps'] < 0):
            raise ValueError('Warmup steps must be a nonnegative integer')
        for rule in config['rules']:
            QLearner(env.n_states, env.n_actions, {**config['learner_defaults'], 'rule':rule}, config['gamma'])
        for sign, eta in itertools.product(config['sign_conventions'], config['margins']):
            FAA(env, target, {**config['faa'], 'eta':eta, 'sign_convention':sign}, 0, 0)


def jobs(config):
    for design, rule, C, delta, eta, sign in itertools.product(
            config['designs'], config['rules'], config['budgets'], config['delta_limits'],
            config['margins'], config['sign_conventions']):
        condition = {'design':design, 'learner':{**config['learner_defaults'], 'rule':rule},
                     'C':C, 'Delta':delta, 'eta':eta, 'sign':sign}
        cid = digest(condition)
        # Only collapse genuinely deterministic configurations, not stochastic MDPs.
        deterministic = rule == 'ucb' and design['environment'].get('slip', 0) == 0
        for seed in range(1 if deterministic else config['seeds']):
            yield {'id':f'{cid}-{seed:06d}', 'condition_id':cid, 'condition':condition, 'seed':seed}


class RecoveryTracker:
    def __init__(self, length):
        self.length = length
        self.times = {name:None for name in EVENTS}
        self.streak = {'q':0, 'greedy':0}
        self.recurred = {'q':False, 'greedy':False, 'target_loss':False}
        self.target_steps = 0

    def observe(self, u, q_good, greedy_good, target):
        if not target and self.times['target_loss'] is None:
            self.times['target_loss'] = u
        elif target and self.times['target_loss'] is not None:
            self.recurred['target_loss'] = True
        for name, good in [('q', q_good), ('greedy', greedy_good)]:
            first = name+'_recovery'
            confirmation = name+'_confirmation'
            if good:
                if self.times[first] is None:
                    self.times[first] = u
                self.streak[name] += 1
                if self.streak[name] >= self.length and self.times[confirmation] is None:
                    self.times[confirmation] = u
            else:
                if self.times[first] is not None:
                    self.recurred[name] = True
                self.streak[name] = 0
        if u > 0:
            self.target_steps += int(target)


def snapshot(learner, state, q_star):
    return {'q':learner.q.tolist(), 'counts':learner.counts.tolist(), 'state':int(state),
            'q_error':float(np.max(np.abs(learner.q-q_star)))}


def run_job(config, job):
    c = job['condition']; design = c['design']; spec = c['learner']; seed = job['seed']
    env = build_mdp(design['environment']); q_star = env.optimal_q(config['gamma'])
    targets = build_targets(env, design['targets'])
    target_states = np.flatnonzero(~targets.all(axis=1))
    init = design['initialization']; shape = q_star.shape
    if init['mode'] == 'controlled':
        q0 = q_star.copy()
        raw = np.asarray(init['counts'])
        counts = np.full(shape, raw.item()) if raw.ndim == 0 else raw
        base = QLearner(*shape, spec, config['gamma'], q0, counts)
    else:
        base = QLearner(*shape, spec, config['gamma'], np.full(shape, init.get('q0',0.)))
    state = env.start
    if init['mode'] == 'warmup':
        arng = np.random.default_rng(np.random.SeedSequence([seed,101]))
        erng = np.random.default_rng(np.random.SeedSequence([seed,102]))
        for _ in range(init['steps']):
            action = base.select(state, arng)
            nxt, reward, done = env.step(state, action, erng)
            base.update(state, action, reward, nxt, done)
            state = env.start if done else nxt
    initial = snapshot(base, state, q_star)
    attacker = FAA(env, targets, {**config['faa'], 'eta':c['eta'], 'sign_convention':c['sign']}, c['Delta'], c['C'])
    A, H = config['attack_steps'], config['post_steps']
    arms = {}
    for arm in ('clean','faa'):
        learner = copy.deepcopy(base); state = initial['state']
        arng = np.random.default_rng(np.random.SeedSequence([seed,201]))
        erng = np.random.default_rng(np.random.SeedSequence([seed,202]))
        tracker = RecoveryTracker(config['confirmation'])
        totals = {phase:{'reward':0.,'goals':0,'updates':0} for phase in ('attack','recovery')}
        visits = {phase:np.zeros(shape, dtype=int) for phase in totals}
        first_update = np.full(shape, -1, dtype=int)
        first_visit = np.full(env.n_states, -1, dtype=int)
        altered = np.zeros(shape, dtype=bool)
        altered_branches = {'promotion':0, 'demotion':0}
        sweep_seen = np.zeros(shape, dtype=bool); sweeps = []
        spent_by = {purpose:0. for purpose in ('navigation','teaching','maintenance')}
        spent_to_hit = None; hit = None; hit_spend = None
        clip_delta = clip_budget = 0; trace = []; attack_log = []
        last_poison = None; target_attack_steps = 0
        for t in range(A+H+1):
            m = margins(learner.q, targets)
            success = bool(np.all(m > attacker.tolerance))
            error = float(np.max(np.abs(learner.q-q_star)))
            selected = learner.q.argmax(axis=1)
            good_policy = bool(np.all(q_star[np.arange(env.n_states), selected] >= q_star.max(axis=1)-1e-10))
            spent = attacker.budget.spent if arm == 'faa' else 0.
            if t <= A:
                if success and hit is None:
                    hit, hit_spend, spent_to_hit = t, spent, spent_by.copy()
                if t > 0:
                    target_attack_steps += int(success)
            if t == A:
                cutoff = snapshot(learner, state, q_star)
                cutoff['target_success'] = success
            if t >= A:
                tracker.observe(t-A, error <= config['q_tolerance'], good_policy, success)
            if seed in config.get('trace_seeds',[0]) and (t % config['trace_every'] == 0 or t in (A,A+H)):
                trace.append({'t':t, 'state':int(state), 'q':learner.q.tolist(),
                              'counts':learner.counts.tolist(), 'q_error':error,
                              'target_margin':m.tolist(), 'spent':spent,
                              'recovery_sweeps':len(sweeps)})
            if t == A+H:
                break
            phase = 'attack' if t < A else 'recovery'
            action = learner.select(state, arng)
            nxt, reward, done = env.step(state, action, erng)
            decision = attacker.decide(learner,state,action,reward,nxt,done) if arm == 'faa' and t < A else AttackDecision()
            clean = learner.clean_candidate(state,action,reward,nxt,done)
            alpha = learner.update(state,action,reward,nxt,done,decision.delta)
            if t < A and arm == 'faa':
                if decision.delta != 0:
                    altered[state,action] = True; last_poison = t+1
                    altered_branches['promotion' if decision.delta > 0 else 'demotion'] += 1
                clip_delta += int(decision.capped_by_delta); clip_budget += int(decision.capped_by_budget)
                spent_by[decision.purpose] += abs(decision.delta)
                # Every intervention opportunity is retained, even when budget is exhausted.
                attack_log.append([t+1,int(state),int(action),int(nxt),bool(done),float(reward),
                                   decision.requested,decision.delta,alpha,decision.purpose,
                                   decision.active_target,decision.capped_by_delta,decision.capped_by_budget,
                                   clean,float(learner.q[state,action])])
            totals[phase]['reward'] += reward
            totals[phase]['goals'] += int(done); totals[phase]['updates'] += 1
            visits[phase][state,action] += 1
            if t >= A:
                u = t-A+1
                if first_visit[state] == -1: first_visit[state] = u
                if first_update[state,action] == -1: first_update[state,action] = u
                sweep_seen[state,action] = True
                if sweep_seen.all():
                    sweeps.append({'u':u,'q_error':float(np.max(np.abs(learner.q-q_star)))})
                    sweep_seen[:] = False
            state = env.start if done else nxt
        arms[arm] = {'cutoff':cutoff, 'final':snapshot(learner,state,q_star),
                     'attainment_time':hit, 'attainment_spend':hit_spend, 'spending_to_attainment':spent_to_hit,
                     'attained_by_cutoff':hit is not None, 'initial_target_success':hit == 0,
                     'spent':spent, 'spending_by_purpose':spent_by,
                     'clip_delta_count':clip_delta, 'clip_budget_count':clip_budget,
                     'last_nonzero_poison_step':last_poison, 'poisoned_entries':altered.tolist(),
                     'nonzero_poison_branches':altered_branches,
                     'events':tracker.times, 'recurrence':tracker.recurred,
                     'target_occupancy':tracker.target_steps/H, 'attack_target_occupancy':target_attack_steps/A,
                     'totals':totals, 'visits':{k:v.tolist() for k,v in visits.items()},
                     'first_state_visit':first_visit.tolist(), 'first_entry_update':first_update.tolist(),
                     'sweeps':sweeps, 'trace':trace, 'attack_log':attack_log}
    if c['C'] == 0 or c['Delta'] == 0:
        for key in ('cutoff','final','events','totals','visits'):
            assert arms['clean'][key] == arms['faa'][key], ('Zero-cap pair diverged',key)
    assert arms['faa']['spent'] <= c['C']+1e-9
    assert all(abs(row[7]) <= c['Delta']+1e-9 for row in arms['faa']['attack_log'])
    return {**job, 'schema':SCHEMA, 'initial':initial, 'q_star':q_star.tolist(),
            'target_states':target_states.tolist(), 'targets':targets.tolist(), 'arms':arms,
            'attack_log_columns':['step','state','action','successor','terminated','reward','requested_delta',
                                  'delta','alpha','purpose','active_target','clipped_delta','clipped_budget',
                                  'clean_candidate','updated_value']}


def run_suite(config_path, out, resume=False, limit=None, dry_run=False):
    config = read_json(config_path); validate(config)
    schedule = list(jobs(config)); out = Path(out)
    if limit is not None and limit < 1: raise ValueError('limit must be positive')
    print(f'Expected paired jobs: {len(schedule)}; output: {out.resolve()}', flush=True)
    if dry_run: return
    manifest = {'schema':SCHEMA,'config':config,'source_hashes':source_hash(),
                'expected_jobs':len(schedule),'python':platform.python_version(),'numpy':np.__version__}
    old_path = out/'manifest.json'
    if old_path.exists():
        if not resume: raise ValueError('Output already exists; use --resume or a new output folder')
        old = read_json(old_path)
        for key in ('schema','config','source_hashes'):
            if old[key] != manifest[key]: raise ValueError(f'Resume refused: {key} changed')
    else:
        if out.exists() and any(out.iterdir()): raise ValueError('Refusing nonempty output without manifest')
        atomic_json(old_path,manifest)
    valid_ids = {j['id'] for j in schedule}
    unexpected = [p.name for p in (out/'records').glob('*.json.gz') if p.name[:-8] not in valid_ids]
    if unexpected: raise ValueError('Unexpected records in output folder')
    completed = 0; new = 0; started = time.monotonic()
    try:
        for job in schedule:
            path = out/'records'/(job['id']+'.json.gz')
            if path.exists():
                saved = read_json(path)
                if saved['id'] != job['id'] or saved['condition'] != job['condition']:
                    raise ValueError('Existing record identity mismatch')
                completed += 1; continue
            if limit is not None and new >= limit: break
            result = run_job(config,job); atomic_json(path,result)
            new += 1; completed += 1
            if new == 1 or new % 10 == 0:
                print(f'Saved {completed}/{len(schedule)} pairs; new={new}; elapsed={time.monotonic()-started:.1f}s',flush=True)
    finally:
        saved_count = len(list((out/'records').glob('*.json.gz')))
        atomic_json(out/'status.json',{'completed_pairs':saved_count,'expected_pairs':len(schedule),'complete':saved_count==len(schedule)})
    print(f'Saved pairs: {saved_count}/{len(schedule)}. Resume safely with --resume.',flush=True)
