"""Experiment orchestration; every run is independent and fully identified."""
import csv
import hashlib
import itertools
import json
import platform
import sys
from pathlib import Path
import numpy as np

from . import __version__
from .mdp import build_mdp, build_targets
from .learner import QLearner
from .faa import FAA, margins


def write_json(path, obj):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def validate_config(config):
    if config.get("experiment") not in {"attack", "controlled_recovery"}:
        raise ValueError("experiment must be attack or controlled_recovery")
    if not config.get("learners") or not config.get("scenarios"):
        raise ValueError("Supply nonempty learners and scenarios")
    if not config.get("seeds") or len(set(config["seeds"])) != len(config["seeds"]):
        raise ValueError("Supply unique, nonempty integer seeds")
    if any(not isinstance(seed, int) or seed < 0 for seed in config["seeds"]):
        raise ValueError("Seeds must be nonnegative integers")
    names = [x["name"] for x in config["learners"]]
    if len(names) != len(set(names)):
        raise ValueError("Learner names must be unique")
    names = [x["name"] for x in config["scenarios"]]
    if len(names) != len(set(names)):
        raise ValueError("Scenario names must be unique")
    if not 0 <= float(config.get("gamma", 0.9)) < 1:
        raise ValueError("Require 0<=gamma<1")
    for field in ["post_steps", "log_every", "eval_every", "recovery_window"]:
        if int(config.get(field, 1)) < 1:
            raise ValueError(f"{field} must be positive")
    if config.get("recovery_metric", "q_error") not in {"q_error", "policy", "both"}:
        raise ValueError("Unknown recovery metric")
    if float(config.get("q_tolerance", 0.05)) <= 0:
        raise ValueError("q_tolerance must be positive")
    if config["experiment"] == "attack":
        if int(config.get("attack_steps", 0)) < 1:
            raise ValueError("attack_steps must be positive")
        if not config.get("delta_limits") or not config.get("budgets"):
            raise ValueError("Provide delta_limits and budgets (null means no total cap)")
        for value in config["delta_limits"]:
            if not np.isfinite(value) or value < 0:
                raise ValueError("Delta limits must be nonnegative and finite")
        for value in config["budgets"]:
            if value is not None and (not np.isfinite(value) or value < 0):
                raise ValueError("Budgets must be nonnegative finite numbers or null")


def jobs_for(config):
    jobs = []
    for scenario, learner, seed in itertools.product(
        config["scenarios"], config["learners"], config["seeds"]
    ):
        base = {"scenario": scenario, "learner": learner, "seed": int(seed)}
        if config["experiment"] == "controlled_recovery":
            jobs.append({**base, "attack": "controlled_initialization", "delta": None, "budget": None})
        else:
            # One clean baseline, not duplicated for each budget/Delta combination.
            jobs.append({**base, "attack": "none", "delta": None, "budget": None})
            if config.get("clean_only", False):
                continue
            for delta, budget in itertools.product(config["delta_limits"], config["budgets"]):
                job = {**base, "attack": "faa", "delta": float(delta), "budget": budget}
                if job not in jobs:
                    jobs.append(job)
    return jobs


def initial_tables(env, q_star, scenario, controlled):
    counts = np.zeros_like(q_star, dtype=np.int64)
    if not controlled:
        initialization = scenario.get("initial_q", "zeros")
        if initialization not in {"zeros", "optimal"}:
            raise ValueError("initial_q must be zeros or optimal")
        q = q_star.copy() if initialization == "optimal" else np.zeros_like(q_star)
        return q, counts
    init = scenario.get("initialization", {})
    distortion = float(init.get("distortion", 2.0))
    if distortion <= 0 or not np.isfinite(distortion):
        raise ValueError("Controlled distortion must be positive and finite")
    q = q_star.copy()
    method = init.get("method", "depress_optimal")
    if method == "depress_optimal":
        optimal = np.isclose(q_star, q_star.max(axis=1, keepdims=True), atol=1e-10, rtol=0)
        q[optimal] -= distortion
    elif method == "explicit":
        q = np.asarray(init["q"], dtype=float)
    else:
        raise ValueError("Controlled method must be depress_optimal or explicit")
    raw_counts = np.asarray(init.get("counts", 0))
    if raw_counts.ndim == 0:
        raw_counts = np.full_like(q_star, raw_counts, dtype=float)
    elif raw_counts.ndim == 1 and env.n_states == 1:
        raw_counts = raw_counts[None, :]
    return q, raw_counts


def run_one(config, job, run_dir):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario, spec = job["scenario"], job["learner"]
    env = build_mdp(scenario["environment"])
    targets = build_targets(env, scenario["targets"])
    gamma = float(config.get("gamma", 0.9))
    q_star = env.optimal_q(gamma)
    controlled = config["experiment"] == "controlled_recovery"
    q0, counts0 = initial_tables(env, q_star, scenario, controlled)
    learner = QLearner(env.n_states, env.n_actions, spec, gamma, q0, counts0)
    counts0 = learner.counts.copy()
    attacker = (FAA(env, targets, config.get("faa", {}), job["delta"], job["budget"])
                if job["attack"] == "faa" else None)
    attack_steps = 0 if controlled else int(config["attack_steps"])
    post_steps = int(config["post_steps"])
    total_steps = attack_steps + post_steps
    log_every = int(config.get("log_every", 10))
    eval_every = int(config.get("eval_every", 100))
    tolerance = float(config.get("faa", {}).get("ranking_tolerance", 1e-10))
    q_tolerance = float(config.get("q_tolerance", 0.05))
    recovery_window = int(config.get("recovery_window", 50))
    recovery_metric = config.get("recovery_metric", "q_error")
    rng_action = np.random.default_rng(np.random.SeedSequence([job["seed"], 227]))
    rng_env = np.random.default_rng(np.random.SeedSequence([job["seed"], 911]))
    state = env.start
    first_hit = None
    cost_to_hit = None
    recovery_confirmation = None
    recovery_window_start = None
    recovery_relapsed = False
    streak = 0
    attack_success_steps = post_success_steps = 0
    target_action_visits = target_action_selected = 0
    target_visits_by_phase = {"attack": 0, "recovery": 0}
    target_actions_by_phase = {"attack": 0, "recovery": 0}
    rewards_by_phase = {"attack": 0.0, "recovery": 0.0}
    total_reward = 0.0
    nonzero_attacks = capped_delta = capped_budget = 0
    spending = {"navigation": 0.0, "teaching": 0.0, "maintenance": 0.0}
    spending_to_hit = None
    state_spending = np.zeros(env.n_states)
    q_cutoff = counts_cutoff = None
    sweep_seen = np.zeros_like(targets, dtype=bool)
    completed_sweeps = 0
    sweep_rows = []
    events = []
    evaluation = []
    fields = ["step", "phase", "state", "q_error", "optimal_greedy", "target_success",
              "target_fraction", "min_target_margin", "spent", "true_reward_cumulative",
              "post_complete_sweeps", "recovery_criterion", "recovery_streak"]
    transition_fields = ["step", "phase", "state", "action", "next_state", "terminated",
                         "reward", "delta", "requested_delta", "alpha", "purpose",
                         "active_target", "capped_by_delta", "capped_by_budget"]
    transition_file = None
    if config.get("save_transitions", False):
        transition_file = (run_dir / "transitions.csv").open("w", newline="")
        transition_writer = csv.DictWriter(transition_file, fieldnames=transition_fields)
        transition_writer.writeheader()
    try:
        with (run_dir / "trajectory.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for t in range(total_steps + 1):
                phase = "attack" if t < attack_steps else "recovery"
                spent = attacker.budget.spent if attacker else 0.0
                target_margins = margins(learner.q, targets)
                success = bool(np.all(target_margins > tolerance))
                greedy = learner.q.argmax(axis=1)
                optimal = bool(np.all(q_star[np.arange(env.n_states), greedy]
                                      >= q_star.max(axis=1) - 1e-9))
                error = float(np.max(np.abs(learner.q - q_star)))
                criterion = (error <= q_tolerance if recovery_metric == "q_error" else
                             optimal if recovery_metric == "policy" else
                             optimal and error <= q_tolerance)
                if t <= attack_steps and success and first_hit is None:
                    first_hit, cost_to_hit = t, spent
                    spending_to_hit = spending.copy()
                    events.append({"event": "first_target_hit", "step": t, "spent": spent})
                if t == attack_steps:
                    q_cutoff, counts_cutoff = learner.q.copy(), learner.counts.copy()
                if t >= attack_steps:
                    streak = streak + 1 if criterion else 0
                    if recovery_confirmation is None and streak >= recovery_window:
                        recovery_confirmation = t - attack_steps
                        recovery_window_start = recovery_confirmation - recovery_window + 1
                        events.append({"event": "recovery_window_confirmed", "step": t})
                    elif recovery_confirmation is not None and not criterion:
                        recovery_relapsed = True
                if t < total_steps:
                    if t < attack_steps:
                        attack_success_steps += int(success)
                    else:
                        post_success_steps += int(success)
                if t % log_every == 0 or t in {attack_steps, total_steps}:
                    writer.writerow(dict(zip(fields, [t, phase, state, error, int(optimal),
                        int(success), float(np.mean(target_margins > tolerance)),
                        float(target_margins.min()), spent, total_reward, completed_sweeps,
                        int(criterion), streak])))
                if t % eval_every == 0 or t in {attack_steps, total_steps}:
                    probabilities = np.eye(env.n_actions)[greedy]
                    values = env.evaluate_policy(probabilities, gamma)
                    evaluation.append({"step": t, "greedy_true_return": float(values[env.start]),
                                       "optimal_true_return": float(q_star[env.start].max())})
                if t == total_steps:
                    break
                action = learner.select(state, rng_action)
                successor, reward, terminated = env.step(state, action, rng_env)
                if not targets[state].all():
                    target_action_visits += 1
                    target_action_selected += int(targets[state, action])
                    target_visits_by_phase[phase] += 1
                    target_actions_by_phase[phase] += int(targets[state, action])
                decision = (attacker.decide(learner, state, action, reward, successor, terminated)
                            if attacker is not None and t < attack_steps else None)
                delta = decision.delta if decision else 0.0
                if decision:
                    nonzero_attacks += int(abs(delta) > 1e-14)
                    capped_delta += int(decision.capped_by_delta)
                    capped_budget += int(decision.capped_by_budget)
                    spending[decision.purpose] += abs(delta)
                    state_spending[state] += abs(delta)
                alpha = learner.update(state, action, reward, successor, terminated, delta)
                total_reward += reward
                rewards_by_phase[phase] += reward
                if t >= attack_steps:
                    sweep_seen[state, action] = True
                    if sweep_seen.all():
                        completed_sweeps += 1
                        sweep_rows.append({"step": t + 1, "sweep": completed_sweeps,
                                           "q_error": float(np.max(np.abs(learner.q - q_star)))})
                        sweep_seen[:] = False
                if transition_file is not None:
                    transition_writer.writerow(dict(zip(transition_fields, [t, phase, state,
                        action, successor, int(terminated), reward, delta,
                        decision.requested if decision else 0.0, alpha,
                        decision.purpose if decision else "none",
                        decision.active_target if decision else -1,
                        int(decision.capped_by_delta) if decision else 0,
                        int(decision.capped_by_budget) if decision else 0])))
                state = env.start if terminated else successor
    finally:
        if transition_file is not None:
            transition_file.close()
    np.savez_compressed(run_dir / "snapshots.npz", q_initial=q0, counts_initial=counts0,
                        q_cutoff=q_cutoff, counts_cutoff=counts_cutoff,
                        q_final=learner.q, counts_final=learner.counts, q_star=q_star,
                        targets=targets, state_spending=state_spending,
                        post_update_counts=learner.counts - counts_cutoff,
                        state_labels=np.asarray(env.labels), action_names=np.asarray(env.action_names))
    write_json(run_dir / "job.json", job)
    write_json(run_dir / "events.json", events)
    write_json(run_dir / "sweeps.json", sweep_rows)
    with (run_dir / "evaluation.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["step", "greedy_true_return", "optimal_true_return"])
        writer.writeheader()
        writer.writerows(evaluation)
    result = {
        "scenario": scenario["name"], "learner": spec["name"], "rule": spec["rule"],
        "experiment": config["experiment"], "attack": job["attack"], "seed": job["seed"],
        "delta_limit": job["delta"], "budget_limit": job["budget"],
        "attack_steps": attack_steps, "post_steps": post_steps,
        "initial_target_success": bool(np.all(margins(q0, targets) > tolerance)),
        "hit_by_attack_deadline": first_hit is not None,
        "first_hit_step": first_hit, "cost_to_hit": cost_to_hit,
        "hit_censored": first_hit is None, "spending_to_hit": spending_to_hit,
        "spent": attacker.budget.spent if attacker else 0.0,
        "spending_by_purpose": spending, "nonzero_attacks": nonzero_attacks,
        "requests_capped_by_delta": capped_delta, "requests_capped_by_budget": capped_budget,
        "attack_target_occupancy": attack_success_steps / attack_steps if attack_steps else None,
        "post_target_occupancy": post_success_steps / post_steps,
        "target_action_frequency": (target_action_selected / target_action_visits
                                    if target_action_visits else None),
        "attack_target_action_frequency": (target_actions_by_phase["attack"] / target_visits_by_phase["attack"]
                                            if target_visits_by_phase["attack"] else None),
        "post_target_action_frequency": (target_actions_by_phase["recovery"] / target_visits_by_phase["recovery"]
                                          if target_visits_by_phase["recovery"] else None),
        "recovery_metric": recovery_metric, "q_tolerance": q_tolerance,
        "recovery_window": recovery_window,
        "recovery_confirmed": recovery_confirmation is not None,
        "recovery_confirmation_steps": recovery_confirmation,
        "recovery_window_start_steps": recovery_window_start,
        "recovery_censored": recovery_confirmation is None,
        "recovery_relapsed_after_confirmation": recovery_relapsed,
        "recovery_time_capped": recovery_confirmation if recovery_confirmation is not None else post_steps,
        "cutoff_q_error": float(np.max(np.abs(q_cutoff - q_star))),
        "final_q_error": float(np.max(np.abs(learner.q - q_star))),
        "post_complete_sweeps": completed_sweeps,
        "true_reward_attack": rewards_by_phase["attack"],
        "true_reward_post": rewards_by_phase["recovery"],
        "true_reward_total": total_reward,
        "final_greedy_true_return": evaluation[-1]["greedy_true_return"],
    }
    # summary is the completion marker, written last and atomically.
    write_json(run_dir / "summary.json", result)
    return result


def run_suite(config_path, output, resume=False, limit=None):
    config_path = Path(config_path)
    config = json.loads(config_path.read_text())
    validate_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    metadata_path = output / "metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if metadata["config_sha256"] != fingerprint:
            raise ValueError("Output directory belongs to a different config; choose a new --out")
        if not resume:
            raise ValueError("Output exists; use --resume or choose a new directory")
    else:
        if any(output.iterdir()):
            raise ValueError("Nonempty output directory has no metadata; choose a new directory")
        write_json(metadata_path, {"config_sha256": fingerprint, "config": config,
                   "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
                   "package_version": __version__, "argv": sys.argv,
                   "note": "Independent reconstruction; no exact-paper-reproduction claim."})
    jobs = jobs_for(config)
    if limit is not None:
        jobs = jobs[:limit]
    for i, job in enumerate(jobs):
        run_id = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()[:16]
        run_dir = output / "runs" / run_id
        if resume and (run_dir / "summary.json").exists():
            print(f"[{i+1}/{len(jobs)}] skip {run_id}", flush=True)
            continue
        print(f"[{i+1}/{len(jobs)}] {job['scenario']['name']} / {job['learner']['name']} / "
              f"{job['attack']} C={job['budget']} Delta={job['delta']} seed={job['seed']}", flush=True)
        run_one(config, job, run_dir)
    return output
