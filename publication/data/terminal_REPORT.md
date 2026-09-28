# Executed validation — 2026-09-16

## Scope and settings

Two deterministic terminal actions, mu=(1,0), alpha=.9, epsilon=.1, temperature=.2,
beta=1, initial Q=mu, initial counts=(100,100), Delta=C=3. Exactly one corrected
FAA intervention. Condition separately on demotion/promotion where the selected
rule assigns that action positive probability. Recovery threshold .05 and
20-observation confirmation window. Clean horizon 2000.

There are 300 seeds per epsilon-greedy/softmax condition and one deterministic
UCB trajectory per feasible condition. 2,404 jobs were requested: 2,402 paired
FAA/clean jobs completed and two impossible UCB promotion requests were skipped.
UCB repetition across seeds would not supply new evidence in this environment.
The validation simulation took approximately 8 seconds on the available runtime;
this is not a runtime promise for another machine or larger warm-up sweeps.

## Demotion results: recovery confirmation, not first revisit

| Rule | Margin | Observed mean | Exact theoretical mean | Bootstrap 95% interval for restricted mean |
| --- | ---: | ---: | ---: | --- |
| epsilon-greedy | .01 | 39.38 | 40.05 | [37.24, 41.75] |
| epsilon-greedy | 1 | 39.38 | 40.05 | [37.23, 41.64] |
| softmax | .01 | 21.95 | 22.06 | [21.80, 22.11] |
| softmax | 1 | 173.24 | 169.43 | [156.69, 191.04] |
| UCB-style | .01 | 32 | 32 | deterministic |
| UCB-style | 1 | >2000 (censored) | no recovery through 2000 | deterministic |

All stochastic demotion runs recovered by H, so observed and restricted sample
means coincide here. The theoretical full mean is not generally the theoretical
restricted mean. For UCB's last row, 2000 is a restricted time, NOT its recovery
or a full mean. No finite exact mean is reported for that row.

Actual spend is (1+eta)/.9, approximately 1.1222 or 2.2222. Both caps are respected.
The clean controls start and stay at the true Q values; their Q recovery time is
0 and their confirmation time is 19. Matching epsilon-greedy results across margins
also reflect the common random numbers and same two repair probabilities.

Correction to an earlier conversational estimate: the small-margin softmax
confirmation prediction is 22.0624, NOT 21.6. The exact calculation is
(1+exp(.01/.2)) + (1+exp(-.899/.2)) + 19.

All 64 stochastic condition/arm/metric CDF comparisons lay within their individual
95% DKW bands. This is reassuring validation, not proof or a universal ranking;
these diagnostics are correlated and are not a familywise statistical test.
Promotion data, clean arms and all four event definitions are included in the raw
and summary files rather than silently pooled into the demotion table.

## Other verification

- All 22 unit/integration tests passed, including the original 12 tests.
- New checks cover a closed-form geometric-sum distribution, theoretical means,
  promotion/demotion and ties, independent UCB prediction versus learner execution,
  both budget caps, retained warm-up counts, impossible branch handling, censored
  restricted means, resumability/config guards, and eligibility of theory overlays.
- The smoke suite completed 77 paired jobs and skipped four impossible conditional
  UCB branches. It includes a small actual clean warm-up experiment. It is a code
  check, not a adequately powered pretraining study.
- A representative survival plot was visually checked.

## Not run

The 500-seed full count/margin sweep, separate cap sweep, and large constant- or
diminishing-learning-rate warm-up sweeps have not been run. Multi-state experiments
from the original project remain available, but their conclusions do not follow
from the one-state theory. See configs/ and use --dry-run/--limit/--resume.
