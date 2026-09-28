"""FAA reconstruction with explicit margin semantics and pathwise budget limits.

Default `corrected`: undesired action is demoted to max(desired)-eta.
Optional `paper_printed`: reproduce the +eta in Eq. (8)'s undesired branch.
The latter does NOT enforce the intended ranking invariant. Neither variant
is claimed to reproduce unpublished author code exactly.
"""
from dataclasses import dataclass
import numpy as np


def margins(q, targets):
    states = np.flatnonzero(~targets.all(axis=1))
    return np.array([
        q[s, targets[s]].max() - q[s, ~targets[s]].max() for s in states
    ])


def greedy_perturbation(q_row, action, desired, clean_value, alpha, eta,
                        sign_convention="corrected"):
    desired = np.asarray(desired, dtype=bool)
    if not np.any(desired):
        raise ValueError("Desired action set must not be empty")
    if np.all(desired):
        return 0.0
    if desired[action]:
        return float(max(0.0, np.max(q_row[~desired]) + eta - clean_value) / alpha)
    sign = -1 if sign_convention == "corrected" else 1
    if sign_convention not in {"corrected", "paper_printed"}:
        raise ValueError("Unknown FAA sign convention")
    return float(min(0.0, np.max(q_row[desired]) + sign * eta - clean_value) / alpha)


@dataclass
class AttackDecision:
    delta: float = 0.0
    requested: float = 0.0
    capped_by_delta: bool = False
    capped_by_budget: bool = False
    purpose: str = "none"
    active_target: int = -1


class Budget:
    def __init__(self, delta_limit, cumulative_limit):
        self.delta_limit = float(delta_limit)
        self.limit = float("inf") if cumulative_limit is None else float(cumulative_limit)
        if not np.isfinite(self.delta_limit) or self.delta_limit < 0:
            raise ValueError("Delta must be finite and nonnegative")
        if self.limit < 0 or np.isnan(self.limit):
            raise ValueError("C must be nonnegative, or null for no cumulative cap")
        self.spent = 0.0

    @property
    def remaining(self):
        return max(0.0, self.limit - self.spent)

    def apply(self, requested, purpose, active_target):
        if not np.isfinite(requested):
            raise FloatingPointError("Nonfinite FAA request")
        step_limited = float(np.clip(requested, -self.delta_limit, self.delta_limit))
        available = self.remaining
        delta = float(np.clip(step_limited, -available, available))
        self.spent += abs(delta)
        if self.spent > self.limit + 1e-9:
            raise AssertionError("Cumulative corruption budget exceeded")
        return AttackDecision(delta, requested,
                              abs(requested) > self.delta_limit + 1e-12,
                              abs(step_limited) > available + 1e-12,
                              purpose, active_target)


class FAA:
    def __init__(self, env, targets, spec, delta_limit, cumulative_limit):
        self.targets = targets.copy()
        self.eta = float(spec.get("eta", 0.01))
        self.tolerance = float(spec.get("ranking_tolerance", 1e-10))
        self.sign = spec.get("sign_convention", "corrected")
        if not self.eta > self.tolerance >= 0:
            raise ValueError("Require eta > ranking_tolerance >= 0")
        if self.sign not in {"corrected", "paper_printed"}:
            raise ValueError("Invalid sign convention")
        epsilon = float(spec.get("navigation_epsilon", 0.1))
        self.budget = Budget(delta_limit, cumulative_limit)
        states = np.flatnonzero(~targets.all(axis=1))
        navigation = {}
        distance = {}
        for s in states:
            nav, hitting_time = env.navigation_policy(int(s), epsilon)
            navigation[int(s)] = nav
            distance[int(s)] = float(hitting_time[env.start])
        self.order = sorted(map(int, states), key=lambda s: (-distance[s], s))
        self.navigation = navigation

    def decide(self, learner, state, action, reward, successor, terminated):
        q = learner.q
        active_index = None
        for i, target in enumerate(self.order):
            row = self.targets[target]
            if q[target, row].max() - q[target, ~row].max() <= self.tolerance:
                active_index = i
                break
        if active_index is None:
            desired = self.targets[state]
            purpose, active_target = "maintenance", -1
        else:
            active_target = self.order[active_index]
            fixed = self.order[:active_index + 1]
            if state in fixed:
                desired = self.targets[state]
                purpose = "teaching" if state == active_target else "maintenance"
            else:
                desired = np.zeros(q.shape[1], dtype=bool)
                desired[self.navigation[active_target][state]] = True
                purpose = "navigation"
        clean = learner.clean_candidate(state, action, reward, successor, terminated)
        requested = greedy_perturbation(
            q[state], action, desired, clean, learner.learning_rate(state, action),
            self.eta, self.sign,
        )
        return self.budget.apply(requested, purpose, active_target)
