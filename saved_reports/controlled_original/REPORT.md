# Multi-state FAA experiment report

Completed paired jobs: **3606/3606**. Complete.

## What was run

Warmup or controlled initialization → 500 attack transitions → 5000 clean transitions. Each pair runs to the full horizon. FAA uses the documented demotion convention and both caps. This is a reconstruction/transfer study, not a literal reproduction of the source paper.

Common learner settings: `{"alpha": 0.9, "alpha_schedule": "constant", "beta": 1.0, "epsilon": 0.1, "temperature": 0.2}`. Gamma=0.9; accuracy tolerance=0.05; confirmation=20 observations. Ties select the lowest action index. UCB uses local state counts. Fixed navigation settings: `{"navigation_epsilon": 0.1, "ranking_tolerance": 1e-10}`.

Complete environments, initializations, targets, signs, seeds and simulation code hashes: [manifest.json](manifest.json). Analysis parameters and source hash: [analysis_settings.json](analysis_settings.json).

## Primary results

Q recovery uses all runs. Target-loss persistence is conditional on success at cessation; its sample size can differ between learners. RMST is E[min(T,H)], not an estimate of an uncensored mean when censoring occurs.

| Design | Rule | C / Delta / eta / sign | n | Ever attained | At cutoff | Actual spend | Q RMST | Q censored | Conditional target-loss n / RMST | Recovery reward loss |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| controlled_counts100_chain3 | epsilon_greedy | 1.0 / 3.0 / 0.01 / corrected | 300 | 0.9367 | 0.1033 | 0.9938 | 3576 | 162 | 31 / 463.5 | 0.11 |
| controlled_counts100_chain3 | softmax | 1.0 / 3.0 / 0.01 / corrected | 300 | 0.5733 | 0 | 1 | 129.7 | 0 | 0 / — | -1.239 |
| controlled_counts100_chain3 | ucb | 1.0 / 3.0 / 0.01 / corrected | 1 | 1 | 0 | 1 | 5000 | 1 | 0 / — | 0 |
| controlled_counts100_chain3 | epsilon_greedy | 3.0 / 3.0 / 0.01 / corrected | 300 | 1 | 0.28 | 2.709 | 3813 | 173 | 84 / 452.8 | 0.3007 |
| controlled_counts100_chain3 | softmax | 3.0 / 3.0 / 0.01 / corrected | 300 | 0.9233 | 0.4033 | 2.731 | 376.4 | 0 | 121 / 168.3 | -5.643 |
| controlled_counts100_chain3 | ucb | 3.0 / 3.0 / 0.01 / corrected | 1 | 1 | 1 | 2.172 | 5000 | 1 | 1 / 5000 | 0 |
| controlled_counts100_chain3 | epsilon_greedy | 10.0 / 3.0 / 0.01 / corrected | 300 | 1 | 0.79 | 5.68 | 3961 | 181 | 237 / 400.1 | 0.8543 |
| controlled_counts100_chain3 | softmax | 10.0 / 3.0 / 0.01 / corrected | 300 | 0.9967 | 0.9967 | 3.598 | 603.1 | 0 | 299 / 167.1 | -10.74 |
| controlled_counts100_chain3 | ucb | 10.0 / 3.0 / 0.01 / corrected | 1 | 1 | 1 | 2.172 | 5000 | 1 | 1 / 5000 | 0 |
| controlled_counts1_chain3 | epsilon_greedy | 1.0 / 3.0 / 0.01 / corrected | 300 | 0.9367 | 0.1033 | 0.9938 | 3576 | 162 | 31 / 463.5 | 0.11 |
| controlled_counts1_chain3 | softmax | 1.0 / 3.0 / 0.01 / corrected | 300 | 0.5733 | 0 | 1 | 129.7 | 0 | 0 / — | -1.239 |
| controlled_counts1_chain3 | ucb | 1.0 / 3.0 / 0.01 / corrected | 1 | 1 | 0 | 1 | 5000 | 1 | 0 / — | 4.4 |
| controlled_counts1_chain3 | epsilon_greedy | 3.0 / 3.0 / 0.01 / corrected | 300 | 1 | 0.28 | 2.709 | 3813 | 173 | 84 / 452.8 | 0.3007 |
| controlled_counts1_chain3 | softmax | 3.0 / 3.0 / 0.01 / corrected | 300 | 0.9233 | 0.4033 | 2.731 | 376.4 | 0 | 121 / 168.3 | -5.643 |
| controlled_counts1_chain3 | ucb | 3.0 / 3.0 / 0.01 / corrected | 1 | 1 | 1 | 1.363 | 5000 | 1 | 1 / 129 | -7.7 |
| controlled_counts1_chain3 | epsilon_greedy | 10.0 / 3.0 / 0.01 / corrected | 300 | 1 | 0.79 | 5.68 | 3961 | 181 | 237 / 400.1 | 0.8543 |
| controlled_counts1_chain3 | softmax | 10.0 / 3.0 / 0.01 / corrected | 300 | 0.9967 | 0.9967 | 3.598 | 603.1 | 0 | 299 / 167.1 | -10.74 |
| controlled_counts1_chain3 | ucb | 10.0 / 3.0 / 0.01 / corrected | 1 | 1 | 1 | 1.363 | 5000 | 1 | 1 / 129 | -7.7 |

## Clean-baseline diagnostic

Whole-table accuracy may remain poor even without poisoning. Read the clean baseline alongside the FAA result; a censored Q-recovery time alone does not identify attack-induced delay. Repeated clean results across budgets use the same seeds and are not independent replications.

| Design | Rule | C | n | Clean Q RMST | Clean Q censored | Initial Q-error mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| controlled_counts100_chain3 | ucb | 10.0 | 1 | 0 | 0 | 0 |
| controlled_counts100_chain3 | epsilon_greedy | 3.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | ucb | 1.0 | 1 | 0 | 0 | 0 |
| controlled_counts100_chain3 | softmax | 10.0 | 300 | 0 | 0 | 0 |
| controlled_counts100_chain3 | softmax | 1.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | softmax | 1.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | epsilon_greedy | 1.0 | 300 | 0 | 0 | 0 |
| controlled_counts100_chain3 | ucb | 1.0 | 1 | 0 | 0 | 0 |
| controlled_counts1_chain3 | ucb | 10.0 | 1 | 0 | 0 | 0 |
| controlled_counts100_chain3 | ucb | 3.0 | 1 | 0 | 0 | 0 |
| controlled_counts100_chain3 | softmax | 3.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | ucb | 3.0 | 1 | 0 | 0 | 0 |
| controlled_counts100_chain3 | epsilon_greedy | 1.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | epsilon_greedy | 10.0 | 300 | 0 | 0 | 0 |
| controlled_counts100_chain3 | epsilon_greedy | 10.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | epsilon_greedy | 3.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | softmax | 3.0 | 300 | 0 | 0 | 0 |
| controlled_counts1_chain3 | softmax | 10.0 | 300 | 0 | 0 | 0 |

## Measurement files

- [summary.csv](summary.csv): attainment and all recovery endpoints, both arms, cohort sizes, censoring, quartiles, restricted means and bootstrap intervals.
- [conditions.csv](conditions.csv): attainment proportions and Wilson intervals; clipping rates; actual spend and its purpose; initial Q error.
- [paired_differences.csv](paired_differences.csv): paired reward/goal loss and recovery-delay differences with bootstrap intervals.
- [runs.csv](runs.csv): per-run endpoints, recurrence, occupancy, error, sweeps, and full-horizon reward/goal totals.
- [coverage.csv](coverage.csv): state/action first visits, inherited counts, entry errors, and update totals. Altered-entry flags refer to the FAA arm for both paired arms.
- [survival.csv](survival.csv): exact empirical staircase at event times; marginal Wilson intervals. Hold each value constant until the next event time.
- Raw compressed records in the input folder retain Q/count snapshots, complete sweep endpoints, and every FAA request/applied perturbation. Keep them for reproducibility.

## Interpretation limits

These outputs separate attainment from persistence and task damage. Failure to attain is not robust recovery from a successful attack. Longer waiting or Q-error delay is not automatically larger reward loss. Real warmup changes values and count imbalance; controlled initialization isolates designated factors. No universal ranking or general multi-state UCB convergence theorem follows from these plots.

Intervals are marginal 95% intervals, not simultaneous guarantees. Identical deterministic UCB runs are collapsed to one; no sampling intervals are shown for those conditions. Shared seeds across budgets/designs induce dependence. Conditional target-loss samples can be small and selectively different. Blank values mean unavailable, not zero.

## Figures

### controlled_counts100_chain3: C=1.0, full

![controlled_counts100_chain3: C=1.0, full](plots/survival_controlled_counts100_chain3_C1-0_Delta3-0_eta0-01_corrected_full.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts100_chain3: C=1.0, zoom

![controlled_counts100_chain3: C=1.0, zoom](plots/survival_controlled_counts100_chain3_C1-0_Delta3-0_eta0-01_corrected_zoom.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts100_chain3: C=3.0, full

![controlled_counts100_chain3: C=3.0, full](plots/survival_controlled_counts100_chain3_C3-0_Delta3-0_eta0-01_corrected_full.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts100_chain3: C=3.0, zoom

![controlled_counts100_chain3: C=3.0, zoom](plots/survival_controlled_counts100_chain3_C3-0_Delta3-0_eta0-01_corrected_zoom.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts100_chain3: C=10.0, full

![controlled_counts100_chain3: C=10.0, full](plots/survival_controlled_counts100_chain3_C10-0_Delta3-0_eta0-01_corrected_full.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts100_chain3: C=10.0, zoom

![controlled_counts100_chain3: C=10.0, zoom](plots/survival_controlled_counts100_chain3_C10-0_Delta3-0_eta0-01_corrected_zoom.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts1_chain3: C=1.0, full

![controlled_counts1_chain3: C=1.0, full](plots/survival_controlled_counts1_chain3_C1-0_Delta3-0_eta0-01_corrected_full.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts1_chain3: C=1.0, zoom

![controlled_counts1_chain3: C=1.0, zoom](plots/survival_controlled_counts1_chain3_C1-0_Delta3-0_eta0-01_corrected_zoom.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts1_chain3: C=3.0, full

![controlled_counts1_chain3: C=3.0, full](plots/survival_controlled_counts1_chain3_C3-0_Delta3-0_eta0-01_corrected_full.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts1_chain3: C=3.0, zoom

![controlled_counts1_chain3: C=3.0, zoom](plots/survival_controlled_counts1_chain3_C3-0_Delta3-0_eta0-01_corrected_zoom.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts1_chain3: C=10.0, full

![controlled_counts1_chain3: C=10.0, full](plots/survival_controlled_counts1_chain3_C10-0_Delta3-0_eta0-01_corrected_full.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### controlled_counts1_chain3: C=10.0, zoom

![controlled_counts1_chain3: C=10.0, zoom](plots/survival_controlled_counts1_chain3_C10-0_Delta3-0_eta0-01_corrected_zoom.png)

All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.

### Budget comparison: controlled_counts100_chain3

![Budget comparison: controlled_counts100_chain3](plots/budgets_controlled_counts100_chain3-3-0-0-01-corrected.png)

Allocated budget is the controlled setting. Actual spend is reported separately. Positive reward loss means the attacked arm earned less. UCB deterministic points have no sampling interval.

### Budget comparison: controlled_counts1_chain3

![Budget comparison: controlled_counts1_chain3](plots/budgets_controlled_counts1_chain3-3-0-0-01-corrected.png)

Allocated budget is the controlled setting. Actual spend is reported separately. Positive reward loss means the attacked arm earned less. UCB deterministic points have no sampling interval.

### Mechanism trace: controlled_counts100_chain3, epsilon_greedy

![Mechanism trace: controlled_counts100_chain3, epsilon_greedy](plots/mechanism_controlled_counts100_chain3-epsilon_greedy-3-0-0-01-corrected_C3.0_seed0.png)

A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.

### Mechanism trace: controlled_counts100_chain3, softmax

![Mechanism trace: controlled_counts100_chain3, softmax](plots/mechanism_controlled_counts100_chain3-softmax-3-0-0-01-corrected_C3.0_seed0.png)

A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.

### Mechanism trace: controlled_counts100_chain3, ucb

![Mechanism trace: controlled_counts100_chain3, ucb](plots/mechanism_controlled_counts100_chain3-ucb-3-0-0-01-corrected_C3.0_seed0.png)

A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.

### Mechanism trace: controlled_counts1_chain3, epsilon_greedy

![Mechanism trace: controlled_counts1_chain3, epsilon_greedy](plots/mechanism_controlled_counts1_chain3-epsilon_greedy-3-0-0-01-corrected_C3.0_seed0.png)

A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.

### Mechanism trace: controlled_counts1_chain3, softmax

![Mechanism trace: controlled_counts1_chain3, softmax](plots/mechanism_controlled_counts1_chain3-softmax-3-0-0-01-corrected_C3.0_seed0.png)

A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.

### Mechanism trace: controlled_counts1_chain3, ucb

![Mechanism trace: controlled_counts1_chain3, ucb](plots/mechanism_controlled_counts1_chain3-ucb-3-0-0-01-corrected_C3.0_seed0.png)

A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.

