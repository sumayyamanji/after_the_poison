# Reproduction levels and limits

## Source and evidence identity

The simulation files are copied without editing. Their hashes match the original manifests for both main chain experiments and the terminal validation. Configuration filenames have been simplified, but the JSON configuration content is unchanged. `provenance/SOURCE_SHA256.json` records the bundled reference inputs. `verify_records.py` checks the raw archives directly, without requiring extraction.

The new wrapper, input-merging script and documentation organise existing work. They do not alter FAA, Q-learning updates, action selection, seeds, environments or recorded outcomes. FAA uses the documented demotion-sign adaptation; it is not claimed to reproduce unpublished author code exactly.

## Statistical and computational details

Original chain settings: 300 seeds per stochastic condition and one deterministic UCB trajectory per condition. Initial counts 1/100 are prescribed values, not actual pretraining. The terminal validation has 300 stochastic seeds and deterministic UCB cases, with two impossible conditional branch requests explicitly recorded as skipped.

For chain analysis the original report script uses bootstrap seed 773; the audit uses 7735. Each uses 1,000 bootstrap draws. These are marginal intervals. Point estimates, random bootstrap intervals and rendered image pixels have different reproducibility requirements. Preserve the saved tables when citing the reported intervals; compare a reanalysis before replacing them.

Original chain manifests report Python 3.14.6 and NumPy 2.5.2. The terminal validation reports Python 3.12.14 and NumPy 2.3.5. These are recorded provenance, not a claim that one common environment generated all results. `requirements.txt` provides dependency ranges; `requirements-tested.txt` pins the environment used for this packaging check. A different environment can change random streams, numerical details or fonts. No container image or universal bitwise guarantee is supplied.

## Raw records are not complete logs of every clean transition

The main chain raw files retain the full attack-window log, exact recorded recovery events, endpoint tables/counts, phase rewards and selected sampled traces. Full post-attack per-transition traces are reconstructed for selected deterministic-environment replays. The word “raw” refers to the original saved job files; it does not mean every transition from every run was logged.

## Reanalysis from original records

`python reproduce.py reanalyse` expands the records and runs the original report/audit implementations. Existing non-empty report output directories are refused to avoid mixing runs. To repeat analysis, choose another `--out`, for example `--out outputs/reanalysis_02`.

To substitute a newly regenerated terminal analysis into a new plotting workspace:

```powershell
python reproduce.py figures --out outputs/terminal_reanalysis_figures
Copy-Item outputs/reanalysis/terminal_validation/summary.csv outputs/terminal_reanalysis_figures/data/terminal_summary.csv
Copy-Item outputs/reanalysis/terminal_validation/survival.csv outputs/terminal_reanalysis_figures/data/terminal_survival.csv
python outputs/terminal_reanalysis_figures/tools/make_missing_figures.py
```

Use your actual reanalysis output path if different. Compare the new tables with `saved_reports/terminal_validation/` before using the new exports. This procedure does not silently update the supplied publication files.

## Analyse a fresh simulation rerun

For a newly simulated S2 run:

```powershell
python simulation/analyze_multistep.py --input outputs/fresh_simulations/controlled --out outputs/fresh_reports/controlled_original
python simulation/audit_multistep.py --input outputs/fresh_simulations/controlled --out outputs/fresh_reports/controlled_audit --replay
```

Repeat with `start0` in the four relevant paths. Then:

```powershell
python rebuild_inputs.py --reports outputs/fresh_reports --out outputs/fresh_inputs
python reproduce.py figures --inputs outputs/fresh_inputs --out outputs/fresh_figures
```

For a fresh terminal run:

```powershell
python simulation/analyze_persistence.py --input outputs/fresh_simulations/terminal_validation --max-plots 0
```

Its analysis is written under that raw folder's `analysis/`. The original simulation runners save completed jobs incrementally and check manifests when resuming.

## Earlier warm-up runs

These are supplementary history, not substitutes for the controlled main experiments. Their reports are included because they were supplied in the conversation. Their complete raw records were not supplied. Configurations/code for warm-up exist, but the package does not claim the original 16,016-pair terminal warm-up or 1,803-pair chain warm-up has been reproduced from raw data.

## Validation performed for this archive

See `provenance/RECORD_VERIFICATION.json` and `PACKAGE_VALIDATION.json`. All original job identities and report-alignment checks passed, including 12 independent representative replays. The 36-row combined table and 32-row count sweep match the saved tables. Python figures regenerated, the TikZ diagram compiled, and 35 existing unit tests passed. Full stochastic simulation suites and complete report reanalysis were not rerun during packaging.
