"""One Q-learning update, three explicitly defined action-selection rules."""
import numpy as np


class QLearner:
    def __init__(self, n_states, n_actions, spec, gamma, q0=None, counts0=None):
        self.spec = dict(spec)
        self.kind = spec["rule"]
        self.gamma = float(gamma)
        self.alpha_value = float(spec.get("alpha", 0.9))
        self.schedule = spec.get("alpha_schedule", "constant")
        self.omega = float(spec.get("omega", 0.75))
        self.epsilon = float(spec.get("epsilon", 0.1))
        self.temperature = float(spec.get("temperature", 0.2))
        self.beta = float(spec.get("beta", 1.0))
        if self.kind not in {"epsilon_greedy", "softmax", "ucb"}:
            raise ValueError(f"Unknown action-selection rule {self.kind}")
        if not 0 <= self.gamma < 1 or not 0 < self.alpha_value <= 1:
            raise ValueError("Require 0<=gamma<1 and 0<alpha<=1")
        if not 0 < self.epsilon < 1 or self.temperature <= 0 or self.beta <= 0:
            raise ValueError("Require 0<epsilon<1, temperature>0, beta>0")
        if self.schedule not in {"constant", "per_visit"} or not 0.5 < self.omega <= 1:
            raise ValueError("Use constant or per_visit alpha; omega in (0.5,1]")
        shape = (n_states, n_actions)
        self.q = np.zeros(shape) if q0 is None else np.array(q0, dtype=float, copy=True)
        raw_counts = np.zeros(shape) if counts0 is None else np.asarray(counts0)
        if self.q.shape != shape or raw_counts.shape != shape:
            raise ValueError("Q/count initialization has wrong shape")
        if not np.all(np.isfinite(self.q)) or not np.all(np.isfinite(raw_counts)):
            raise ValueError("Initial values/counts must be finite")
        if np.any(raw_counts < 0) or np.any(raw_counts != np.floor(raw_counts)):
            raise ValueError("Counts must be nonnegative integers")
        self.counts = np.array(raw_counts, dtype=np.int64)

    def probabilities(self, state):
        values = self.q[state]
        k = len(values)
        if self.kind == "epsilon_greedy":
            p = np.full(k, self.epsilon / k)
            p[int(values.argmax())] += 1 - self.epsilon
            return p
        if self.kind == "softmax":
            weights = np.exp((values - values.max()) / self.temperature)
            return weights / weights.sum()
        unvisited = np.flatnonzero(self.counts[state] == 0)
        if len(unvisited):
            action = int(unvisited[0])
        else:
            bonus = self.beta * np.sqrt(
                np.log1p(float(self.counts[state].sum())) / self.counts[state]
            )
            action = int(np.argmax(values + bonus))
        p = np.zeros(k)
        p[action] = 1.0
        return p

    def select(self, state, rng):
        # One draw consumed by every rule; UCB remains deterministic conditional on state.
        return int(rng.choice(self.q.shape[1], p=self.probabilities(state)))

    def learning_rate(self, state, action):
        if self.schedule == "constant":
            return self.alpha_value
        return float((self.counts[state, action] + 1) ** (-self.omega))

    def clean_candidate(self, state, action, reward, next_state, terminated):
        alpha = self.learning_rate(state, action)
        future = 0.0 if terminated else float(self.q[next_state].max())
        return (1 - alpha) * self.q[state, action] + alpha * (reward + self.gamma * future)

    def update(self, state, action, reward, next_state, terminated, delta=0.0):
        alpha = self.learning_rate(state, action)
        self.q[state, action] = self.clean_candidate(
            state, action, reward, next_state, terminated
        ) + alpha * delta
        self.counts[state, action] += 1
        if not np.all(np.isfinite(self.q[state])):
            raise FloatingPointError("Q update produced a nonfinite value")
        return alpha
