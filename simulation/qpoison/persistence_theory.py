"""Exact finite-horizon predictions for deterministic, two-action terminal tasks.

Independent scalar implementation: does not call QLearner. Constant alpha only;
all non-altered Q-values must equal their true rewards. No further poisoning.
Geometric waiting times count the successful selection (support 1,2,...).
"""
import math
import numpy as np

METRICS = ('first_revisit', 'greedy_recovery', 'q_recovery', 'q_confirmation')


def probability(q, action, rule, epsilon, temperature):
    if rule == 'epsilon_greedy':
        return epsilon / 2 + (1 - epsilon if int(np.argmax(q)) == action else 0.)
    x = (q[1-action] - q[action]) / temperature
    return math.exp(-float(np.logaddexp(0., x)))


def geometric_sum(probabilities, horizon, shift=0):
    """Return P(T>t), t=0..H, for independent geometric sums + shift."""
    p = np.asarray(probabilities, float)
    if len(p) == 0:
        survival = (np.arange(horizon+1) < shift).astype(float)
        return survival, float(shift), 0.
    state = np.zeros(len(p)+1); state[0] = 1.
    cdf = np.zeros(horizon+1)
    for t in range(1, horizon+1):
        moved = state[:-1] * p
        state[:-1] -= moved
        state[1:] += moved
        cdf[t] = state[-1]
    if shift:
        cdf = np.concatenate([np.zeros(shift), cdf])[:horizon+1]
    with np.errstate(divide='ignore', over='ignore'):
        mean = float(np.sum(1/p) + shift)
        variance = float(np.sum((1-p)/p**2))
    return np.clip(1-cdf, 0, 1), mean, variance


def predict(q, counts, rewards, altered, spec, horizon, tolerance, window):
    """Predict from the actual post-intervention table, including cap effects.

Returns None outside this theorem's assumptions. UCB predicts deterministically
through H only; it does not turn an unobserved event into a finite mean.
"""
    q = np.array(q, float); counts = np.array(counts, int)
    rewards = np.array(rewards, float)
    if spec.get('alpha_schedule', 'constant') != 'constant':
        return None
    if len(q) != 2 or not np.isclose(q[1-altered], rewards[1-altered], atol=1e-12, rtol=0):
        return None
    alpha = spec['alpha']; rule = spec['rule']; best = int(np.argmax(rewards))
    if rewards[0] == rewards[1]:
        return None
    curves = {}; summaries = {}
    if rule == 'ucb':
        times = {key: None for key in METRICS}; streak = 0
        initial_q = q.copy(); initial_counts = counts.copy()
        for t in range(horizon+1):
            if int(np.argmax(q)) == best and times['greedy_recovery'] is None:
                times['greedy_recovery'] = t
            good = np.max(np.abs(q-rewards)) <= tolerance
            if good and times['q_recovery'] is None: times['q_recovery'] = t
            streak = streak+1 if good else 0
            if streak >= window and times['q_confirmation'] is None:
                times['q_confirmation'] = t
            if t == horizon: break
            if np.any(counts == 0):
                selected = int(np.flatnonzero(counts == 0)[0])
            else:
                scores = q + spec['beta'] * np.sqrt(np.log1p(float(counts.sum())) / counts)
                selected = int(np.argmax(scores))
            if selected == altered and times['first_revisit'] is None:
                times['first_revisit'] = t+1
            q[selected] = (1-alpha)*q[selected] + alpha*rewards[selected]
            counts[selected] += 1
        for metric, time in times.items():
            curves[metric] = np.ones(horizon+1) if time is None else (np.arange(horizon+1)<time).astype(float)
            summaries[metric] = {'mean': time, 'variance': 0. if time is not None else None,
                                 'exact_time_within_horizon': time}
        bound = None
        gap = initial_q[1-altered] - initial_q[altered]
        if gap > 0 and initial_counts[altered] > 0 and np.all(initial_counts > 0):
            bound = float(initial_counts[altered] * gap**2 / spec['beta']**2)
        return {'curves': curves, 'summaries': summaries, 'ucb_log_total_count_lower_bound': bound}

    # Enumerate deterministic Q after j repairs; the random part is the waiting.
    probabilities = []; greedy_r = q_r = None
    for j in range(100000):
        if greedy_r is None and int(np.argmax(q)) == best: greedy_r = j
        if q_r is None and np.max(np.abs(q-rewards)) <= tolerance: q_r = j
        if greedy_r is not None and q_r is not None and j >= 1: break
        probabilities.append(probability(q, altered, rule, spec['epsilon'], spec['temperature']))
        q[altered] = (1-alpha)*q[altered] + alpha*rewards[altered]
    else:
        raise ValueError('Too many required repairs; choose a practical alpha/tolerance')
    stages = {'first_revisit': (1, 0), 'greedy_recovery': (greedy_r, 0),
              'q_recovery': (q_r, 0), 'q_confirmation': (q_r, window-1)}
    for metric, (r, shift) in stages.items():
        curve, mean, variance = geometric_sum(probabilities[:r], horizon, shift)
        curves[metric] = curve
        summaries[metric] = {'mean': mean, 'variance': variance, 'required_repairs': r}
    return {'curves': curves, 'summaries': summaries, 'ucb_log_total_count_lower_bound': None}
