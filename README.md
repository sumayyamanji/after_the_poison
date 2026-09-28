# After the Poison — reproducibility package

Tabular Q-learning after finite-budget reward poisoning: epsilon-greedy, softmax and a UCB-style selector. The attacker is an independently reconstructed and adapted FAA, with a documented demotion-sign choice, per-step cap and cumulative budget. This is not the original authors' code.

**Start here:** the saved dissertation figures are in [`publication/figures`](publication/figures). [FIGURE_INDEX.md](FIGURE_INDEX.md) links each figure to its exact data and script. You do not need to rerun the experiments to regenerate the figures.

## What is included

| Experiment | Included evidence | Status |
|---|---|---|
| Controlled chain, start/reset S2 | Matching source/configuration, raw archive, original report, audit and replay traces | All 3,606 paired records |
| Controlled chain, start/reset S0 | Matching source/configuration, raw archive, original report, audit and replay traces | All 3,606 paired records |
| Terminal theory validation | Source/configuration, raw archive, summary, survival checkpoints | 2,402 completed pairs and 2 explicitly skipped impossible branch requests; all 2,404 jobs accounted for |
| Deterministic UCB count sweep | Source, 32 exact per-condition checkpoints, tables and plots | Complete, including small-gap extension |
| Earlier terminal warm-up | Exported report/summary and plots | 16,016 pairs reported; original raw records not supplied |
| Earlier chain warm-up | Exported report, per-run summary and plots | 1,803 pairs reported; original raw records not supplied |

The two chain audits reanalyse the original chain experiments; they are **not** another 7,212 independent experiments. Every paired record contains an attacked run and a clean comparison run.

The **full ZIP** contains `raw_archives/` and `writing/`. The smaller **GitHub-ready ZIP** omits those folders, but contains source, configurations, reports, plotting data and figures. It can regenerate the dissertation figures without the large raw archives. Add `raw_archives/` from the full ZIP to use raw verification or reanalysis.

## Install

Use Python 3.10 or newer. From this folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe reproduce.py figures
```

On macOS/Linux, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`. Alternatively activate your environment and use `python` in all commands below. NumPy and Matplotlib are required; a TeX installation is needed only to compile the native TikZ diagram or dissertation.

Outputs are written under `outputs/`, keeping the supplied evidence unchanged. Choose a fresh `--out` directory if a plotting/reanalysis output already exists.

## Four different reproduction tasks

**1. Regenerate figures from saved data (quick; no simulations):**

```powershell
python reproduce.py figures
```

Open `outputs/figure_rebuild/figures/`. To compile the native TikZ Figure 3.1 as well, use `--latex` and a fresh output directory. This requires `pdflatex` on your PATH. A Python-rendered schematic is generated without TeX; the TikZ source is the version used in the current dissertation.

**2. Check the original raw records and selected independent replays:**

```powershell
python reproduce.py verify --replay
```

Requires the full ZIP. Checks all job IDs/settings, original exported arm results, audit expenditure/reward values, reward-change caps and code hashes. Independently replays the lowest-seed C=3 pair in each chain condition: 12 representative pairs. The result is saved to `outputs/record_verification.json`.

**3. Rebuild the statistical analysis from the raw records (no new learning simulations, except selected independent replay checks):**

```powershell
python reproduce.py reanalyse
python rebuild_inputs.py --reports outputs/reanalysis --out outputs/reanalysis_inputs
python reproduce.py figures --inputs outputs/reanalysis_inputs --out outputs/reanalysis_figures
```

The first command expands the supplied archives under `outputs/raw/` and runs the original report/audit scripts. It may take substantially longer than plotting. A figure rebuild using `--inputs` replaces the five chain CSV inputs; terminal and count-sweep inputs remain the supplied reference inputs. To replace terminal inputs too, use the procedure in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

**4. Run the learning experiments again from scratch:**

```powershell
python reproduce.py rerun --experiment controlled --dry-run
python reproduce.py rerun --experiment controlled
python reproduce.py rerun --experiment start0
python reproduce.py rerun --experiment terminal_validation
```

Use `--resume` after interruption; use `--limit 2` for a small check first. These produce fresh records under `outputs/fresh_simulations/`; they do not replace your supplied records. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for analysing those new outputs. Do not mix full-simulation reruns with reanalysis of the original records.

The deterministic count calculation is separate and quick:

```powershell
python reproduce.py sweep
```

It searches for exact integer crossing times and skips unchanged waiting periods; it does not simulate an astronomically long wait one step at a time.

## What was checked when assembling this package

- All 7,212 uploaded chain paired records are present, unique, readable and match the expected configurations.
- The four core chain simulation files match the hashes in both uploaded manifests.
- Exported attainment, expenditure, terminal errors, cutoff status, event times and phase totals agree with the raw arm records within numerical tolerance.
- All 12 selected independent chain replays pass. These check the learner dynamics using recorded reward changes, not an independent implementation of FAA's navigation optimisation.
- All terminal jobs are accounted for, their code hash matches, and completed event times/spending match the saved export.
- The 36-row chain plotting table rebuilds exactly from the saved reports.
- All figure scripts execute, the native TikZ diagram compiles, and the 32-condition count sweep reproduces the saved CSV exactly.
- The existing 35 unit tests pass.

**Not claimed:** a fresh full rerun of all stochastic learning experiments, a bit-for-bit match across arbitrary Python/NumPy versions, or complete raw records for the earlier warm-ups. The original runtime versions are preserved in the manifests; the assembly-check environment is recorded in `provenance/PACKAGE_VALIDATION.json`.

## Folder guide

- `simulation/`: original simulation, attack, learner, analysis and audit code; unchanged core source.
- `manifests/`: original configurations, versions and source hashes.
- `raw_archives/`: compressed records for the main chain and terminal validation experiments (full ZIP).
- `saved_reports/`: complete original report exports and audits; historical files retain their original wording.
- `publication/`: exact saved plotting data, current figures, figure scripts and TikZ source.
- `provenance/`: source hashes and completed verification results.
- `writing/`: the previously delivered concise dissertation PDF/Overleaf ZIP, reattached unchanged (full ZIP). Later copy-and-paste edits, including the proposed revised benefit paragraph, have **not** been silently inserted.
- `outputs/`: generated files, not included in the archive or Git history.

For sharing or publishing, see [SHARING.md](SHARING.md). No repository or external upload has been created on your behalf.
