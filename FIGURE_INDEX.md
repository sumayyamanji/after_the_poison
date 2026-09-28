# Dissertation figure → saved data → code

Figure numbers refer to the concise dissertation included in `writing/`. Use its LaTeX labels if numbering changes. The authoritative supplied files are below; every row also has a reproducible route.

| Figure | Correct saved file | Input | Regeneration |
|---|---|---|---|
| 3.1 `fig:chain-timeline` | [`TikZ PDF`](publication/figures/chain_reset_timeline_tikz.pdf), [`source`](publication/figures/chain_reset_timeline.tex), with [`styles`](publication/figures/chain_tikz_styles.tex) | Declared chain, resets and timing | `python reproduce.py figures --latex`; native output `figures/chain_reset_timeline_tikz.pdf`. `publication/figure3_1.tex` is the standalone wrapper. |
| 5.1 `fig:terminal-overlay` | [`terminal_theory_empirical.pdf`](publication/figures/terminal_theory_empirical.pdf) | `publication/data/terminal_summary.csv`, `terminal_survival.csv` | `publication/tools/make_missing_figures.py` |
| 5.2 `fig:ucb-count-ratio` | [`ucb_count_ratio.pdf`](publication/figures/ucb_count_ratio.pdf) | `publication/data/ucb_count_sweep/records/` (32 exact checkpoints) | `publication/tools/ucb_count_sweep.py` plot function; `reproduce.py figures` copies the ratio export to the dissertation filename |
| 5.3 `fig:attainment` | [`attainment_retention.png`](publication/figures/attainment_retention.png) | `publication/data/COMBINED_CONDITIONS.csv` | `publication/make_figures.py` |
| 5.4 `fig:survival` | [`q_survival.png`](publication/figures/q_survival.png) | `publication/data/S0_runs.csv`, `S2_runs.csv` | `publication/make_figures.py` |
| 5.5 `fig:stateaccess` | [`ucb_state_access.pdf`](publication/figures/ucb_state_access.pdf); PNG alternative has suffix `_readable` | `publication/data/ucb_state_access.csv`; S2, counts 1, C=3, condition `cd120c9fc60950b6`, seed 0 | `publication/tools/reexport_replay_figures.py` |
| 5.6 `fig:actionaccess` | [`ucb_action_access.pdf`](publication/figures/ucb_action_access.pdf); PNG alternative has suffix `_readable` | `publication/data/ucb_action_access.csv`; S0, counts 100, C=3, condition `ff53513639bde55f`, seed 0 | `publication/tools/reexport_replay_figures.py` |
| 5.7 `fig:reward` | [`reward_loss.png`](publication/figures/reward_loss.png) | `publication/data/COMBINED_CONDITIONS.csv` | `publication/make_figures.py` |
| A.1 `fig:sweep-times` | [`count_scaling.pdf`](publication/data/ucb_count_sweep/count_scaling.pdf) | Same 32 checkpoints; requested-range subset | Count-sweep plot function |
| A.2 `fig:sweep-extended` | [`small_gap_extended.pdf`](publication/data/ucb_count_sweep/small_gap_extended.pdf) | Same checkpoints; D=0.1 extension | Count-sweep plot function |

## One command for the Python figures

`python reproduce.py figures` stages a copy of the plotting workspace and regenerates the figures above, without changing the originals. Add `--latex` for the current native diagram. The Python diagram generated without TeX is an alternative rendering of the setup, not the exact TikZ layout.

Historical debug-title replay PNGs remain in the original report exports for provenance. For the dissertation use the PDF or `_readable.png` files identified above.

## Rebuilding the figure inputs

`python rebuild_inputs.py` merges saved original reports and audits into `outputs/rebuilt_inputs`. It reproduces all 36 condition rows and selects the same two replay traces. To plot those reconstructed inputs:

```powershell
python reproduce.py figures --inputs outputs/rebuilt_inputs --out outputs/from_rebuilt_inputs
```

The terminal empirical curves are recorded survival checkpoints, not invented individual event times or interpolated empirical curves. Exact event times are also available in the terminal raw records. The plotting script checks 12 curve/condition combinations against the saved theoretical and event-summary values.

## Tables

- Table 5.1: terminal summary plus the explicit confirmation-window convention in the text.
- Tables 5.2–5.3 and Table 6.1's empirical references: combined condition table and the underlying original/audit reports.
- Full count-sweep table: `publication/data/ucb_count_sweep/complete_table.tex` and `summary.csv`.
- Methods settings and theoretical tables are declared/derived content, not new empirical runs.

## Clocks and interpretation

Original multistep reports measure recovery from the end of the 500-step attack period. Audits measure first recovery from immediately after the last nonzero reward change. Reward comparisons retain the fixed attack/clean windows. These are intentional differences; do not substitute a similarly named column from the other report.

The upper-right panels of Figures 5.5/5.6 follow Right at S0, chosen because it has the largest error immediately after the last reward change. In Run B the entry still wrong at the horizon is Left; it is not the entry plotted in that upper-right panel.
