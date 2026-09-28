"""Finite MDPs with explicit terminal transitions and exact model-based evaluation.

Only decision states occupy Q-table rows. Terminal transitions have next_state=-1.
There is no time-limit termination: rollout cutoffs censor observations and never
change the Bellman target. Real termination resets the next decision to `start`.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Outcome:
    probability: float
    next_state: int
    reward: float
    terminated: bool = False


class TabularMDP:
    def __init__(self, outcomes, start, labels, action_names, name):
        self.outcomes = outcomes
        self.n_states = len(outcomes)
        self.n_actions = len(action_names)
        self.start = int(start)
        self.labels = list(labels)
        self.action_names = list(action_names)
        self.name = name
        if self.n_states < 1 or not 0 <= self.start < self.n_states:
            raise ValueError("Invalid decision states/start state")
        self.P = np.zeros((self.n_states, self.n_actions, self.n_states))
        self.R = np.zeros((self.n_states, self.n_actions))
        self.terminal_probability = np.zeros_like(self.R)
        for s, actions in enumerate(outcomes):
            if len(actions) != self.n_actions:
                raise ValueError("Every state must have the same action set")
            for a, branch in enumerate(actions):
                if not branch or not np.isclose(sum(x.probability for x in branch), 1):
                    raise ValueError("Outcome probabilities must sum to one")
                for x in branch:
                    if not np.isfinite(x.reward) or x.probability < 0:
                        raise ValueError("Invalid reward or probability")
                    self.R[s, a] += x.probability * x.reward
                    if x.terminated:
                        self.terminal_probability[s, a] += x.probability
                    else:
                        if not 0 <= x.next_state < self.n_states:
                            raise ValueError("Nonterminal successor is out of range")
                        self.P[s, a, x.next_state] += x.probability
        # Navigation includes resets; value evaluation does not bootstrap through them.
        self.navigation_P = self.P.copy()
        self.navigation_P[:, :, self.start] += self.terminal_probability

    def step(self, state, action, rng):
        branch = self.outcomes[state][action]
        # Consume one draw even for deterministic transitions for consistent streams.
        u = rng.random()
        cumulative = 0.0
        for x in branch:
            cumulative += x.probability
            if u < cumulative:
                return x.next_state, x.reward, x.terminated
        x = branch[-1]  # Floating-point summation edge.
        return x.next_state, x.reward, x.terminated

    def optimal_q(self, gamma, tolerance=1e-12, max_iterations=100000):
        q = np.zeros_like(self.R)
        for _ in range(max_iterations):
            updated = self.R + gamma * np.einsum("sak,k->sa", self.P, q.max(axis=1))
            if np.max(np.abs(updated - q)) < tolerance:
                return updated
            q = updated
        raise RuntimeError("Value iteration did not converge")

    def evaluate_policy(self, probabilities, gamma):
        """Exact true discounted return until real termination, from each state."""
        probabilities = np.asarray(probabilities, dtype=float)
        if probabilities.shape != self.R.shape or np.any(probabilities < 0):
            raise ValueError("Invalid policy probability shape/values")
        if not np.allclose(probabilities.sum(axis=1), 1):
            raise ValueError("Policy rows must sum to one")
        reward = np.sum(probabilities * self.R, axis=1)
        transition = np.einsum("sa,sak->sk", probabilities, self.P)
        return np.linalg.solve(np.eye(self.n_states) - gamma * transition, reward)

    def navigation_policy(self, goal, epsilon):
        """SSP policy iteration for shortest expected epsilon-greedy hitting time.

        The epsilon is an ATTACKER planning parameter, also used for softmax/UCB
        victims in the transfer experiment. This does not claim their navigation
        is epsilon-greedy or that FAA's original bound transfers.
        """
        if not 0 < epsilon < 1:
            raise ValueError("Navigation epsilon must lie strictly between 0 and 1")
        states = np.array([s for s in range(self.n_states) if s != goal], dtype=int)
        actions = np.zeros(self.n_states, dtype=int)
        distances = np.zeros(self.n_states)
        if len(states) == 0:
            return actions, distances
        random_transition = self.navigation_P.mean(axis=1)
        for _ in range(10000):
            transition = ((1 - epsilon) * self.navigation_P[np.arange(self.n_states), actions]
                          + epsilon * random_transition)
            try:
                distances[states] = np.linalg.solve(
                    np.eye(len(states)) - transition[np.ix_(states, states)],
                    np.ones(len(states)),
                )
            except np.linalg.LinAlgError as exc:
                raise ValueError("Target is not reachable under the navigation model") from exc
            if np.any(distances[states] < -1e-6) or not np.all(np.isfinite(distances)):
                raise ValueError("Invalid navigation hitting times")
            costs = 1 + np.einsum("sak,k->sa", self.navigation_P, distances)
            new_actions = costs.argmin(axis=1)
            new_actions[goal] = 0
            # Preserve a minimizing old action to avoid roundoff cycling on ties.
            old_cost = costs[np.arange(self.n_states), actions]
            keep = old_cost <= costs.min(axis=1) + 1e-10
            new_actions[keep] = actions[keep]
            if np.array_equal(new_actions[states], actions[states]):
                return actions, distances
            actions = new_actions
        raise RuntimeError("Navigation policy iteration failed to stabilize")


def _branches(action, n_actions, transition, slip):
    branches = []
    for actual in range(n_actions):
        probability = (1 - slip if actual == action else 0) + slip / n_actions
        if probability:
            successor, reward, done = transition(actual)
            branches.append(Outcome(probability, successor, reward, done))
    return branches


def build_mdp(spec):
    kind = spec["kind"]
    slip = float(spec.get("slip", 0.0))
    if not 0 <= slip <= 1:
        raise ValueError("slip must be in [0,1]")
    if kind == "chain":
        n = int(spec.get("n_states", 5))
        if n < 2:
            raise ValueError("chain requires >=2 nonterminal states")
        step_reward = float(spec.get("step_reward", -0.1))
        goal_reward = float(spec.get("goal_reward", 1.0))
        outcomes = []
        for s in range(n):
            def transition(a, s=s):
                if a == 0:
                    return max(0, s - 1), step_reward, False
                if s == n - 1:
                    return -1, goal_reward, True
                return s + 1, step_reward, False
            outcomes.append([_branches(a, 2, transition, slip) for a in range(2)])
        return TabularMDP(outcomes, spec.get("start", n - 1),
                          [str(i) for i in range(n)], ["left", "right"], f"chain_{n}")
    if kind == "grid":
        rows, cols = int(spec.get("rows", 5)), int(spec.get("cols", 5))
        goal = tuple(spec.get("goal", [rows - 1, cols - 1]))
        walls = {tuple(x) for x in spec.get("walls", [])}
        cells = [(r, c) for r in range(rows) for c in range(cols)
                 if (r, c) not in walls and (r, c) != goal]
        if goal in walls or not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
            raise ValueError("Invalid grid goal")
        index = {cell: i for i, cell in enumerate(cells)}
        start = tuple(spec.get("start", [rows - 1, 0]))
        if start not in index:
            raise ValueError("Invalid grid start")
        offsets = [(-1, 0), (0, 1), (1, 0), (0, -1)]
        outcomes = []
        for cell in cells:
            def transition(a, cell=cell):
                dr, dc = offsets[a]
                dest = (cell[0] + dr, cell[1] + dc)
                if dest == goal:
                    return -1, float(spec.get("goal_reward", 1)), True
                if dest not in index:
                    dest = cell
                return index[dest], float(spec.get("step_reward", -0.1)), False
            outcomes.append([_branches(a, 4, transition, slip) for a in range(4)])
        env = TabularMDP(outcomes, index[start], [f"{r},{c}" for r, c in cells],
                         ["up", "right", "down", "left"], f"grid_{rows}x{cols}")
        env.cell_index = index
        return env
    if kind == "one_state":
        rewards = list(map(float, spec.get("rewards", [1.0, 0.0])))
        if len(rewards) < 2:
            raise ValueError("one_state needs at least two actions")
        if slip != 0:
            raise ValueError("Use deterministic one_state rewards for controlled recovery")
        return TabularMDP([[[Outcome(1.0, -1, r, True)] for r in rewards]], 0,
                          ["decision"], [f"action_{a}" for a in range(len(rewards))], "one_state")
    raise ValueError(f"Unknown environment kind: {kind}")


def build_targets(env, spec):
    """Boolean acceptable-action mask; all-True rows are don't-care states."""
    mask = np.ones((env.n_states, env.n_actions), dtype=bool)
    if isinstance(spec, str):
        if spec == "chain_policy":
            if not env.name.startswith("chain_"):
                raise ValueError("chain_policy requires a chain")
            mask[:] = False
            mask[0, 0] = True
            mask[1:, 1] = True
        elif spec == "leftmost_only":
            if not env.name.startswith("chain_"):
                raise ValueError("leftmost_only requires a chain")
            mask[0] = False
            mask[0, 0] = True
        elif spec == "suboptimal_action":
            if env.n_states != 1:
                raise ValueError("suboptimal_action preset requires one state")
            mask[0] = False
            mask[0, int(env.R[0].argmin())] = True
        else:
            raise ValueError(f"Unknown target preset: {spec}")
    else:
        for item in spec:
            state = item["state"]
            if isinstance(state, list):
                state = env.cell_index[tuple(state)]
            state = int(state)
            if not 0 <= state < env.n_states:
                raise ValueError("Target state out of range")
            actions = list(map(int, item["actions"]))
            if not actions or min(actions) < 0 or max(actions) >= env.n_actions:
                raise ValueError("Invalid target actions")
            mask[state] = False
            mask[state, actions] = True
    if np.all(mask):
        raise ValueError("At least one constrained target state is required")
    return mask
