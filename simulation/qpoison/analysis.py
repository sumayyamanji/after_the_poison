"""Seed-level summaries, explicit censoring, paired clean comparisons, and plots."""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np


def wilson(successes, count, z=1.95996398454):
    if count == 0:
        return None, None
    rate = successes / count
    denom = 1 + z*z/count
    midpoint = (rate + z*z/(2*count))/denom
    radius = z * math.sqrt(rate*(1-rate)/count + z*z/(4*count*count))/denom
    return max(0., midpoint-radius), min(1., midpoint+radius)


def bootstrap_mean(values, rng, resamples=2000):
    values = np.array([x for x in values if x is not None], dtype=float)
    if len(values) == 0:
        return None, None, None, 0
    if len(values) == 1:
        # One run cannot estimate between-run uncertainty.
        return float(values[0]), None, None, 1
    samples = rng.choice(values, size=(resamples, len(values)), replace=True).mean(axis=1)
    return float(values.mean()), float(np.quantile(samples, .025)), float(np.quantile(samples, .975)), len(values)


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def analyze(output, resamples=2000):
    output = Path(output)
    records = []
    for path in sorted((output / "runs").glob("*/summary.json")):
        record = json.loads(path.read_text())
        record["run_id"] = path.parent.name
        records.append(record)
    if not records:
        raise ValueError("No completed runs found")
    flat = []
    for record in records:
        row = {key: value for key, value in record.items() if not isinstance(value, dict)}
        for purpose, amount in record["spending_by_purpose"].items():
            row[f"spent_{purpose}"] = amount
        flat.append(row)
    write_csv(output / "runs.csv", flat)
    keys = ["experiment", "scenario", "learner", "rule", "attack", "delta_limit", "budget_limit"]
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record[key] for key in keys)].append(record)
    rng = np.random.default_rng(6020915)
    aggregates = []
    metrics = ["spent", "attack_target_occupancy", "post_target_occupancy",
               "attack_target_action_frequency", "post_target_action_frequency",
               "cutoff_q_error", "final_q_error", "true_reward_attack", "true_reward_post",
               "true_reward_total", "final_greedy_true_return", "post_complete_sweeps",
               "recovery_time_capped"]
    for group_key, members in groups.items():
        row = dict(zip(keys, group_key))
        row["n_runs"] = len(members)
        for name in ["hit_by_attack_deadline", "recovery_confirmed"]:
            successes = sum(int(x[name]) for x in members)
            lo, hi = wilson(successes, len(members))
            row[name + "_rate"] = successes / len(members)
            row[name + "_ci_low"], row[name + "_ci_high"] = lo, hi
        for name in metrics:
            mean, lo, hi, n = bootstrap_mean([x[name] for x in members], rng, resamples)
            row[name + "_mean"] = mean
            row[name + "_ci_low"], row[name + "_ci_high"] = lo, hi
            row[name + "_n"] = n
        # Conditional costs are explicitly labeled and never replace success rates.
        values = [x["cost_to_hit"] for x in members if x["hit_by_attack_deadline"]]
        mean, lo, hi, n = bootstrap_mean(values, rng, resamples)
        row.update(cost_to_hit_successes_only_mean=mean, cost_to_hit_successes_only_ci_low=lo,
                   cost_to_hit_successes_only_ci_high=hi, n_successful_hits=n)
        row["n_recovery_censored"] = sum(x["recovery_censored"] for x in members)
        row["n_recovery_relapsed"] = sum(x["recovery_relapsed_after_confirmation"] for x in members)
        aggregates.append(row)
    write_csv(output / "aggregate.csv", aggregates)
    baseline = {(x["scenario"], x["learner"], x["seed"]): x
                for x in records if x["attack"] == "none"}
    paired = []
    for x in records:
        if x["attack"] != "faa":
            continue
        clean = baseline.get((x["scenario"], x["learner"], x["seed"]))
        if clean is None:
            continue
        paired.append({key: x[key] for key in keys + ["seed", "run_id"]} | {
            "clean_minus_attacked_true_reward_attack": clean["true_reward_attack"] - x["true_reward_attack"],
            "clean_minus_attacked_true_reward_post": clean["true_reward_post"] - x["true_reward_post"],
            "clean_minus_attacked_final_greedy_return": clean["final_greedy_true_return"] - x["final_greedy_true_return"],
        })
    write_csv(output / "paired_clean_differences.csv", paired)
    paired_groups = defaultdict(list)
    for row in paired:
        paired_groups[tuple(row[key] for key in keys)].append(row)
    paired_aggregate = []
    for key, members in paired_groups.items():
        row = dict(zip(keys, key)) | {"n_pairs": len(members)}
        for metric in ["clean_minus_attacked_true_reward_attack", "clean_minus_attacked_true_reward_post",
                       "clean_minus_attacked_final_greedy_return"]:
            mean, lo, hi, _ = bootstrap_mean([x[metric] for x in members], rng, resamples)
            row[metric + "_mean"], row[metric + "_ci_low"], row[metric + "_ci_high"] = mean, lo, hi
        paired_aggregate.append(row)
    write_csv(output / "paired_clean_aggregate.csv", paired_aggregate)
    notes = """# Analysis interpretation

- Success probabilities use Wilson 95% intervals across independent run seeds.
- Means use percentile bootstrap 95% intervals across run seeds (not time steps).
- `cost_to_hit_successes_only_*` is conditional on successful attainment. Always
  interpret it with `hit_by_attack_deadline_rate` and `n_successful_hits`.
- `recovery_time_capped` is min(confirmation time, post_steps). Censored runs are
  included at the horizon. This is a restricted-horizon mean, not an uncensored
  expected recovery time. All runs in each group share the same horizon.
- Recovery means a finite window of the configured criterion. It does not prove
  permanent recovery. Relapses after confirmation are reported separately.
- `true_reward_*` is actual undiscounted reward earned during training. Exact
  `greedy_true_return` evaluates the frozen greedy policy under true rewards,
  discounted until real termination. It is not the behavior policy's return.
- Paired differences use clean and attacked runs with the same seed and learner.
  The resulting state/action trajectories are generally different.
- Controlled recovery sets Q/counts directly. Its initial distortion is NOT an
  FAA attack achieved for zero cost; it isolates the recovery mechanism.
- Smoke runs have too few seeds for substantive scientific conclusions.
"""
    (output / "ANALYSIS_NOTES.md").write_text(notes)
    plot_results(output, groups, keys, aggregates)
    print(f"Wrote runs.csv, aggregate.csv, paired comparisons, and plots to {output}")


def plot_results(output, groups, keys, aggregates):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plots = output / "plots"
    plots.mkdir(exist_ok=True)
    def slug(value):
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(value))
    # Matched budgets/Delta within each scenario. Clean baselines are shown in raw summaries.
    for scenario in sorted({x["scenario"] for x in aggregates}):
        deltas = sorted({x["delta_limit"] for x in aggregates
                         if x["scenario"] == scenario and x["attack"] == "faa"})
        for delta in deltas:
            rows = [x for x in aggregates if x["scenario"] == scenario and
                    x["attack"] == "faa" and x["delta_limit"] == delta and x["budget_limit"] is not None]
            if not rows:
                continue
            fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
            for label in sorted({x["learner"] for x in rows}):
                entries = sorted([x for x in rows if x["learner"] == label], key=lambda x: x["budget_limit"])
                for ax, metric, title in zip(axes,
                        ["hit_by_attack_deadline_rate", "post_target_occupancy_mean"],
                        ["Target attained by deadline", "Target occupancy during recovery"]):
                    suffix = "_rate" if metric.endswith("_rate") else "_mean"
                    prefix = metric[:-len(suffix)]
                    x = np.array([z["budget_limit"] for z in entries])
                    y = np.array([z[metric] for z in entries])
                    lo = np.array([z.get(prefix+"_ci_low") if z.get(prefix+"_ci_low") is not None else z[metric] for z in entries])
                    hi = np.array([z.get(prefix+"_ci_high") if z.get(prefix+"_ci_high") is not None else z[metric] for z in entries])
                    ax.plot(x, y, "o-", label=label)
                    ax.fill_between(x, lo, hi, alpha=.12)
                    ax.set(xlabel="Cumulative budget C", ylabel="Fraction", title=title, ylim=(-.03, 1.03))
            axes[0].legend(fontsize=8)
            fig.suptitle(f"{scenario}; per-step bound Delta={delta}")
            fig.savefig(plots / f"budget_{slug(scenario)}_delta_{delta}.png", dpi=160)
            plt.close(fig)
    # Recovery CDF denominator is ALL runs, not just recovered runs.
    comparisons = defaultdict(list)
    for key, members in groups.items():
        identity = dict(zip(keys, key))
        comparison = (identity["scenario"], identity["attack"], identity["delta_limit"], identity["budget_limit"])
        comparisons[comparison].append((identity["learner"], members))
    for comparison, variants in comparisons.items():
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
        for label, members in sorted(variants):
            horizon = members[0]["post_steps"]
            grid = np.linspace(0, horizon, min(201, horizon+1)).astype(int)
            times = [x["recovery_confirmation_steps"] for x in members]
            cdf = [sum(t is not None and t <= point for t in times)/len(times) for point in grid]
            axes[0].step(grid, cdf, where="post", label=f"{label} (n={len(members)})")
            traces = []
            for member in members:
                with (output / "runs" / member["run_id"] / "trajectory.csv").open() as stream:
                    trace = [row for row in csv.DictReader(stream) if row["phase"] == "recovery"]
                traces.append(([int(row["step"]) - member["attack_steps"] for row in trace],
                               [float(row["q_error"]) for row in trace]))
            # Checkpoints are identical within groups; no fabricated interpolation.
            xs = traces[0][0]
            if any(trace[0] != xs for trace in traces):
                raise ValueError("Mismatched trace checkpoints within condition")
            errors = np.asarray([trace[1] for trace in traces])
            axes[1].plot(xs, np.maximum(np.median(errors, axis=0), 1e-14), label=label)
            axes[1].fill_between(xs, np.maximum(np.quantile(errors,.25,axis=0),1e-14),
                                np.maximum(np.quantile(errors,.75,axis=0),1e-14), alpha=.12)
        axes[0].set(xlabel="Clean training steps", ylabel="Fraction confirmed recovered",
                    ylim=(-.02,1.02), title="Recovery CDF (censored runs retained)")
        axes[1].set(xlabel="Clean training steps", ylabel="Max Q error", yscale="log",
                    title="Median Q error; shading is interquartile range")
        axes[0].legend(fontsize=7)
        fig.suptitle(f"{comparison[0]} / {comparison[1]} / Delta={comparison[2]} / C={comparison[3]}")
        filename = "recovery_" + "_".join(map(slug, comparison)) + ".png"
        fig.savefig(plots / filename, dpi=160)
        plt.close(fig)
