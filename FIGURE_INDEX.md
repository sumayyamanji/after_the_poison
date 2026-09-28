# Dissertation figure -> saved data->  code

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

`python reproduce.py figures` stages a copy of the plotting workspace and regenerates the figures above. Add `--latex` for the current native diagram. The Python diagram generated without TeX is an alternative rendering of the setup, not the exact TikZ layout.


## Rebuilding the figure inputs

`python rebuild_inputs.py` merges saved original reports and audits into `outputs/rebuilt_inputs`. It reproduces all 36 condition rows and selects the same two replay traces. To plot those reconstructed inputs:

```powershell
python reproduce.py figures --inputs outputs/rebuilt_inputs --out outputs/from_rebuilt_inputs
```

