# Questions 3 and 5: raw-record audit

Completed records read: **3606/3606**. Complete.

## Clock definitions

Time zero for the new analysis is the table immediately after the final nonzero poisoned update. No-poison runs have no last-poison clock. Every included run has at least 5000 clean transitions after this point; restricted means use this common horizon, avoiding unequal follow-up. Exact first events during the original attack window are reconstructed from logged updates; later events use the saved exact cutoff-relative event times.

Target-loss means include only runs target-successful immediately after the last poison. This differs from conditioning on success at the original cutoff. Last-poison time and the conditioning event are outcome-dependent; these are descriptive comparisons, not randomized interventions at fixed post-attack states. This report measures first recovery, not permanent recovery or a new confirmation-window endpoint.

## Question 3: correction delays

| Design | Rule | C | Nonzero-poison n | Mean last poison | Q RMST from last poison | Q events not seen by common horizon |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| controlled_counts100_chain3 | ucb | 10.0 | 1 | 18 | 5000 | 1 |
| controlled_counts100_chain3 | epsilon_greedy | 3.0 | 300 | 109.8 | 3981 | 178 |
| controlled_counts1_chain3 | ucb | 1.0 | 1 | 112 | 5000 | 1 |
| controlled_counts100_chain3 | softmax | 10.0 | 300 | 355.2 | 746.4 | 0 |
| controlled_counts100_chain3 | softmax | 1.0 | 300 | 13.79 | 375.6 | 0 |
| controlled_counts1_chain3 | softmax | 1.0 | 300 | 13.79 | 375.6 | 0 |
| controlled_counts1_chain3 | epsilon_greedy | 1.0 | 300 | 21.04 | 3776 | 168 |
| controlled_counts100_chain3 | ucb | 1.0 | 1 | 10 | 5000 | 1 |
| controlled_counts1_chain3 | ucb | 10.0 | 1 | 113 | 5000 | 1 |
| controlled_counts100_chain3 | ucb | 3.0 | 1 | 18 | 5000 | 1 |
| controlled_counts100_chain3 | softmax | 3.0 | 300 | 237.6 | 575 | 0 |
| controlled_counts1_chain3 | ucb | 3.0 | 1 | 113 | 5000 | 1 |
| controlled_counts100_chain3 | epsilon_greedy | 1.0 | 300 | 21.04 | 3776 | 168 |
| controlled_counts1_chain3 | epsilon_greedy | 10.0 | 300 | 217.1 | 4081 | 185 |
| controlled_counts100_chain3 | epsilon_greedy | 10.0 | 300 | 217.1 | 4081 | 185 |
| controlled_counts1_chain3 | epsilon_greedy | 3.0 | 300 | 109.8 | 3981 | 178 |
| controlled_counts1_chain3 | softmax | 3.0 | 300 | 237.6 | 575 | 0 |
| controlled_counts1_chain3 | softmax | 10.0 | 300 | 355.2 | 746.4 | 0 |

Entry-level first state visits, first corrective-action opportunities, update counts and error magnitudes are in [entry_coverage.csv](entry_coverage.csv). They cover all time after the last poison through the original endpoint; this follow-up length differs between runs and is explicitly recorded. An action update is an opportunity to repair, not a guarantee of improvement.

## Question 5: environmental reward damage

| Design | Rule | C | Attack loss | Recovery-window loss | Combined loss |
| --- | --- | ---: | ---: | ---: | ---: |
| controlled_counts100_chain3 | ucb | 10.0 | 23.1 | 0 | 23.1 |
| controlled_counts100_chain3 | epsilon_greedy | 3.0 | 24.25 | 0.3007 | 24.56 |
| controlled_counts1_chain3 | ucb | 1.0 | -6.6 | 4.4 | -2.2 |
| controlled_counts100_chain3 | softmax | 10.0 | -7.898 | -10.74 | -18.63 |
| controlled_counts100_chain3 | softmax | 1.0 | -5.845 | -1.239 | -7.084 |
| controlled_counts1_chain3 | softmax | 1.0 | -5.845 | -1.239 | -7.084 |
| controlled_counts1_chain3 | epsilon_greedy | 1.0 | 11.96 | 0.11 | 12.07 |
| controlled_counts100_chain3 | ucb | 1.0 | 14.3 | 0 | 14.3 |
| controlled_counts1_chain3 | ucb | 10.0 | -6.6 | -7.7 | -14.3 |
| controlled_counts100_chain3 | ucb | 3.0 | 23.1 | 0 | 23.1 |
| controlled_counts100_chain3 | softmax | 3.0 | -7.187 | -5.643 | -12.83 |
| controlled_counts1_chain3 | ucb | 3.0 | -6.6 | -7.7 | -14.3 |
| controlled_counts100_chain3 | epsilon_greedy | 1.0 | 11.96 | 0.11 | 12.07 |
| controlled_counts1_chain3 | epsilon_greedy | 10.0 | 44.3 | 0.8543 | 45.15 |
| controlled_counts100_chain3 | epsilon_greedy | 10.0 | 44.3 | 0.8543 | 45.15 |
| controlled_counts1_chain3 | epsilon_greedy | 3.0 | 24.25 | 0.3007 | 24.56 |
| controlled_counts1_chain3 | softmax | 3.0 | -7.187 | -5.643 | -12.83 |
| controlled_counts1_chain3 | softmax | 10.0 | -7.898 | -10.74 | -18.63 |

Loss is paired clean minus FAA, using environmental rewards. Negative values are retained. Combined uncertainty is bootstrapped from each run’s combined loss, not obtained by adding interval endpoints. Compare each start condition against its own clean arm. These phase windows remain the original fixed windows; they are not silently moved to the last-poison time.

## Files and limits

- [runs.csv](runs.csv): exact last-poison first-event times, horizon flags, errors, phase and combined rewards.
- [summary.csv](summary.csv): marginal 95% percentile bootstrap intervals (1,000 draws); no interval for one observation. Not adjusted for multiple comparisons.
- [entry_coverage.csv](entry_coverage.csv): state/action access and repair opportunities, including zero-update entries.
- [manifest.json](manifest.json) and [audit_settings.json](audit_settings.json): original simulation settings and audit provenance.
- Replays, when requested, independently recompute deterministic-chain selection and Q updates using the recorded poison. They do not independently verify FAA’s navigation optimization or prove general causal claims.
- Full per-update replay CSVs contain bootstrap-target error and before/after entry error; a clean update can inherit an inaccurate successor estimate.
- Only selected replays provide full post-cutoff error-versus-update trajectories. No sampled trace is treated as an exact event time.

Independent representative pairs checked: 6. Selection: lowest available seed per condition at allocated C=3.0.

![Representative replay](plots/replay_38ab60ae7a8cc968.png)

![Representative replay](plots/replay_b42e23640bb75c67.png)

![Representative replay](plots/replay_cc7d03a3a03a3325.png)

![Representative replay](plots/replay_cd120c9fc60950b6.png)

![Representative replay](plots/replay_f1058b2831fa7cb3.png)

![Representative replay](plots/replay_fca2b5eeaa547c1f.png)

