# Analysis status
Completed paired jobs: 2402. Skipped impossible branch requests: 2.
Expected jobs: 2404. Partial results are allowed; check completion before interpretation.

All runs share cutoff H=2000. Blank times/quantiles mean unobserved, not zero.
Survival S(t)=P(T>t); restricted mean E[min(T,H)]=sum_(t=0)^(H-1) S(t).
The survival CSV samples at most ~201 time points; calculations use every step.
Bootstrap intervals concern the restricted mean, not an unobserved full mean.
Wilson intervals are pointwise; DKW checks concern one entire CDF at a time.
Across many conditions, occasional DKW failures are expected; these are diagnostics,
not a familywise hypothesis test or proof of correctness. UCB is deterministic here.
First revisit tracks the intervention action even in the paired clean arm.
First recovery is not permanent recovery in arbitrary MDPs. In this deterministic
terminal task, Q-errors cannot increase under clean updates.
Controlled predictions require constant alpha and only one initially inaccurate value.
Warm-up runs do not receive idealized theory overlays. No UCB1 regret theorem is claimed.
The spend plot is descriptive and mixes counts/margins; use condition-level tables
and survival figures for comparisons. C is allowed budget; spent is actual expenditure.
No larger FAA navigation experiment is claimed by this runner. See PERSISTENCE.md.
