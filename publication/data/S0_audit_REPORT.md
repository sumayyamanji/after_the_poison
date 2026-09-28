# Questions 3 and 5: raw-record audit

Completed records read: **3606/3606**. Complete.

## Clock definitions

Time zero for the new analysis is the table immediately after the final nonzero poisoned update. No-poison runs have no last-poison clock. Every included run has at least 5000 clean transitions after this point; restricted means use this common horizon, avoiding unequal follow-up. Exact first events during the original attack window are reconstructed from logged updates; later events use the saved exact cutoff-relative event times.

Target-loss means include only runs target-successful immediately after the last poison. This differs from conditioning on success at the original cutoff. Last-poison time and the conditioning event are outcome-dependent; these are descriptive comparisons, not randomized interventions at fixed post-attack states. This report measures first recovery, not permanent recovery or a new confirmation-window endpoint.

## Question 3: correction delays

| Design | Rule | C | Nonzero-poison n | Mean last poison | Q RMST from last poison | Q events not seen by common horizon |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| controlled_counts100_chain3__start0 | epsilon_greedy | 10.0 | 300 | 76.68 | 46.72 | 0 |
| controlled_counts1_chain3__start0 | ucb | 1.0 | 1 | 12 | 27 | 0 |
| controlled_counts100_chain3__start0 | epsilon_greedy | 1.0 | 300 | 9.427 | 57.19 | 0 |
| controlled_counts1_chain3__start0 | epsilon_greedy | 3.0 | 300 | 24.58 | 58.08 | 0 |
| controlled_counts1_chain3__start0 | ucb | 3.0 | 1 | 39 | 10 | 0 |
| controlled_counts1_chain3__start0 | epsilon_greedy | 1.0 | 300 | 9.427 | 57.19 | 0 |
| controlled_counts100_chain3__start0 | softmax | 1.0 | 300 | 15.4 | 17.86 | 0 |
| controlled_counts1_chain3__start0 | softmax | 1.0 | 300 | 15.4 | 17.86 | 0 |
| controlled_counts100_chain3__start0 | ucb | 1.0 | 1 | 9 | 5000 | 1 |
| controlled_counts100_chain3__start0 | epsilon_greedy | 3.0 | 300 | 24.58 | 58.08 | 0 |
| controlled_counts100_chain3__start0 | softmax | 3.0 | 300 | 49.04 | 26.82 | 0 |
| controlled_counts100_chain3__start0 | ucb | 10.0 | 1 | 114 | 3 | 0 |
| controlled_counts1_chain3__start0 | softmax | 3.0 | 300 | 49.04 | 26.82 | 0 |
| controlled_counts1_chain3__start0 | ucb | 10.0 | 1 | 130 | 24 | 0 |
| controlled_counts100_chain3__start0 | softmax | 10.0 | 300 | 167.1 | 28.47 | 0 |
| controlled_counts1_chain3__start0 | softmax | 10.0 | 300 | 167.1 | 28.47 | 0 |
| controlled_counts1_chain3__start0 | epsilon_greedy | 10.0 | 300 | 76.68 | 46.72 | 0 |
| controlled_counts100_chain3__start0 | ucb | 3.0 | 1 | 30 | 5000 | 1 |

Entry-level first state visits, first corrective-action opportunities, update counts and error magnitudes are in [entry_coverage.csv](entry_coverage.csv). They cover all time after the last poison through the original endpoint; this follow-up length differs between runs and is explicitly recorded. An action update is an opportunity to repair, not a guarantee of improvement.

## Question 5: environmental reward damage

| Design | Rule | C | Attack loss | Recovery-window loss | Combined loss |
| --- | --- | ---: | ---: | ---: | ---: |
| controlled_counts100_chain3__start0 | epsilon_greedy | 10.0 | 21.38 | 0 | 21.38 |
| controlled_counts1_chain3__start0 | ucb | 1.0 | 0 | 0 | 0 |
| controlled_counts100_chain3__start0 | epsilon_greedy | 1.0 | 1.936 | 0 | 1.936 |
| controlled_counts1_chain3__start0 | epsilon_greedy | 3.0 | 6.31 | 0 | 6.31 |
| controlled_counts1_chain3__start0 | ucb | 3.0 | 1.421e-14 | 0 | 1.421e-14 |
| controlled_counts1_chain3__start0 | epsilon_greedy | 1.0 | 1.936 | 0 | 1.936 |
| controlled_counts100_chain3__start0 | softmax | 1.0 | 0.319 | 0 | 0.319 |
| controlled_counts1_chain3__start0 | softmax | 1.0 | 0.319 | 0 | 0.319 |
| controlled_counts100_chain3__start0 | ucb | 1.0 | 2.2 | -18.7 | -16.5 |
| controlled_counts100_chain3__start0 | epsilon_greedy | 3.0 | 6.31 | 0 | 6.31 |
| controlled_counts100_chain3__start0 | softmax | 3.0 | 1.188 | 0 | 1.188 |
| controlled_counts100_chain3__start0 | ucb | 10.0 | 13.2 | -13.2 | -3.723e-12 |
| controlled_counts1_chain3__start0 | softmax | 3.0 | 1.188 | 0 | 1.188 |
| controlled_counts1_chain3__start0 | ucb | 10.0 | -1.421e-14 | 0 | -1.421e-14 |
| controlled_counts100_chain3__start0 | softmax | 10.0 | 4.587 | 0 | 4.587 |
| controlled_counts1_chain3__start0 | softmax | 10.0 | 4.587 | 0 | 4.587 |
| controlled_counts1_chain3__start0 | epsilon_greedy | 10.0 | 21.38 | 0 | 21.38 |
| controlled_counts100_chain3__start0 | ucb | 3.0 | 5.5 | -18.7 | -13.2 |

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

![Representative replay](plots/replay_54f69fe2e38933e0.png)

![Representative replay](plots/replay_556f9db582af7718.png)

![Representative replay](plots/replay_77afd18ff442be1d.png)

![Representative replay](plots/replay_afff6b3fa18a1458.png)

![Representative replay](plots/replay_d5551db993abd10a.png)

![Representative replay](plots/replay_ff53513639bde55f.png)

