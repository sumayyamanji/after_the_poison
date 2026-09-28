# Reproduction levels and limits


## Statistical and computational details

Original chain settings: 300 seeds per stochastic condition and one deterministic UCB trajectory per condition. Initial counts 1/100. The terminal validation has 300 stochastic seeds and deterministic UCB cases. 

For chain analysis the original report script uses bootstrap seed 773; the audit uses 7735. Each uses 1,000 bootstrap draws. 

Point estimates, random bootstrap intervals and rendered image pixels have different reproducibility requirements. 

Original chain manifests report Python 3.14.6 and NumPy 2.5.2. The terminal validation reports Python 3.12.14 and NumPy 2.3.5. 

`requirements.txt` provides dependency ranges; `requirements-tested.txt` pins the environment used for this packaging check. 


## Reanalysis from original records

`python reproduce.py reanalyse` expands the records and runs the original report/audit implementations. 

To repeat analysis, choose another `--out`, for example `--out outputs/reanalysis_02`.

To substitute a newly regenerated terminal analysis into a new plotting workspace:

```powershell
python reproduce.py figures --out outputs/terminal_reanalysis_figures
Copy-Item outputs/reanalysis/terminal_validation/summary.csv outputs/terminal_reanalysis_figures/data/terminal_summary.csv
Copy-Item outputs/reanalysis/terminal_validation/survival.csv outputs/terminal_reanalysis_figures/data/terminal_survival.csv
python outputs/terminal_reanalysis_figures/tools/make_missing_figures.py
```

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

Its analysis is written under that raw folder's `analysis/`. 

