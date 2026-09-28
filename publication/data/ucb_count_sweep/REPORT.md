# UCB count-scaling results

All counts are post-attack. Q starts at (-D, 0), with true values (1, 0).
Every event time is finite and computed, not censored. W and T in the CSV are full integers.
Large values printed below use scientific notation for readability; W and T may look equal after rounding although T-W=1.
Initial tables and counts are prescribed; this sweep does not measure whether on-policy FAA can create every configuration.

| n_a | n_c regime | D | W | T_rho | predicted log W | computed log W | ratio | adjacent slope | slope error |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | fixed_1 | 0.1 | 2 | 3 | 0.01 | 0.69314718 | 69.314718 | — | — |
| 3 | fixed_1 | 0.1 | 4 | 5 | 0.03 | 1.3862944 | 46.209812 | 0.34657359 | 0.33657359 |
| 10 | fixed_1 | 0.1 | 15 | 16 | 0.1 | 2.7080502 | 27.080502 | 0.18882226 | 0.17882226 |
| 30 | fixed_1 | 0.1 | 55 | 56 | 0.3 | 4.0073332 | 13.357777 | 0.064964149 | 0.054964149 |
| 100 | fixed_1 | 0.1 | 287 | 288 | 1 | 5.6594822 | 5.6594822 | 0.023602129 | 0.013602129 |
| 300 | fixed_1 | 0.1 | 2089 | 2090 | 3 | 7.6444408 | 2.5481469 | 0.0099247927 | -7.5207271e-05 |
| 1000 | fixed_1 | 0.1 | 145140 | 145141 | 10 | 11.885454 | 1.1885454 | 0.0060585904 | -0.0039414096 |
| 3000 | fixed_1 | 0.1 | 1.0697218E+13 | 1.0697218E+13 | 30 | 30.001005 | 1.0000335 | 0.0090577754 | -0.00094222463 |
| 10000 | fixed_1 | 0.1 | 2.6881171E+43 | 2.6881171E+43 | 100 | 100 | 1 | 0.0099998565 | -1.4354537e-07 |
| 1 | matched | 0.1 | 2 | 3 | 0.01 | 0.69314718 | 69.314718 | — | — |
| 3 | matched | 0.1 | 2 | 3 | 0.03 | 0.69314718 | 23.104906 | 0 | -0.01 |
| 10 | matched | 0.1 | 6 | 7 | 0.1 | 1.7917595 | 17.917595 | 0.15694461 | 0.14694461 |
| 30 | matched | 0.1 | 26 | 27 | 0.3 | 3.2580965 | 10.860322 | 0.073316853 | 0.063316853 |
| 100 | matched | 0.1 | 188 | 189 | 1 | 5.236442 | 5.236442 | 0.028262077 | 0.018262077 |
| 300 | matched | 0.1 | 1790 | 1791 | 3 | 7.4899709 | 2.496657 | 0.011267645 | 0.0012676447 |
| 1000 | matched | 0.1 | 144141 | 144142 | 10 | 11.878547 | 1.1878547 | 0.0062693948 | -0.0037306052 |
| 3000 | matched | 0.1 | 1.0697218E+13 | 1.0697218E+13 | 30 | 30.001005 | 1.0000335 | 0.0090612288 | -0.00093877122 |
| 10000 | matched | 0.1 | 2.6881171E+43 | 2.6881171E+43 | 100 | 100 | 1 | 0.0099998565 | -1.4354533e-07 |
| 1 | fixed_1 | 0.5 | 3 | 4 | 0.25 | 1.0986123 | 4.3944492 | — | — |
| 3 | fixed_1 | 0.5 | 13 | 14 | 0.75 | 2.5649494 | 3.4199325 | 0.73316853 | 0.48316853 |
| 10 | fixed_1 | 0.5 | 123 | 124 | 2.5 | 4.8121844 | 1.9248737 | 0.32103357 | 0.071033571 |
| 30 | fixed_1 | 0.5 | 5929 | 5930 | 7.5 | 8.6876108 | 1.1583481 | 0.19377132 | -0.056228676 |
| 100 | fixed_1 | 0.5 | 72139075393 | 72139075394 | 25 | 25.001862 | 1.0000745 | 0.23306073 | -0.016939274 |
| 300 | fixed_1 | 0.5 | 3.7332420E+32 | 3.7332420E+32 | 75 | 75 | 1 | 0.24999069 | -9.3084775e-06 |
| 1000 | fixed_1 | 0.5 | 3.7464546E+108 | 3.7464546E+108 | 250 | 250 | 1 | 0.25 | -1.9209266e-16 |
| 1 | matched | 0.5 | 3 | 4 | 0.25 | 1.0986123 | 4.3944492 | — | — |
| 3 | matched | 0.5 | 11 | 12 | 0.75 | 2.3978953 | 3.1971937 | 0.64964149 | 0.39964149 |
| 10 | matched | 0.5 | 114 | 115 | 2.5 | 4.7361984 | 1.8944794 | 0.33404331 | 0.084043311 |
| 30 | matched | 0.5 | 5900 | 5901 | 7.5 | 8.6827076 | 1.1576944 | 0.19732546 | -0.052674541 |
| 100 | matched | 0.5 | 72139075294 | 72139075295 | 25 | 25.001862 | 1.0000745 | 0.23313077 | -0.016869228 |
| 300 | matched | 0.5 | 3.7332420E+32 | 3.7332420E+32 | 75 | 75 | 1 | 0.24999069 | -9.3084706e-06 |
| 1000 | matched | 0.5 | 3.7464546E+108 | 3.7464546E+108 | 250 | 250 | 1 | 0.25 | -1.9209266e-16 |

Independent step-by-step checks passed in 20/32 conditions; others exceed the declared check limit.
Every integer boundary was certified. Observed T_rho - W values: [1].

## How to read the comparison
The proposition predicts the ratio tends to 1. It does not assert a straight line at small counts.
`adjacent_slope` uses this count and the preceding tested count within the same gap/regime.
`slope_error` = adjacent_slope - D^2/beta^2; `ratio_error` = log(W)/(n_a D^2/beta^2) - 1.
The first row of each series has no adjacent slope. This is a deterministic numerical study, not a statistical test.

## Figures
[Requested-range scaling](count_scaling.png) · [Vector PDF](count_scaling.pdf)
[Asymptotic ratios](asymptotic_ratio.png) · [Vector PDF](asymptotic_ratio.pdf)
[Small-gap extended range](small_gap_extended.png) · [Vector PDF](small_gap_extended.pdf)

No confidence intervals are appropriate: there is no seed randomness in this design.
The full recovery simulation uses the exact counts after the skipped constant-value waiting period.
Gamma=0.9 is recorded for consistency but terminal updates have zero bootstrap.

Numerical computation and verification time: 1.70 seconds (machine-dependent; excludes plotting).
