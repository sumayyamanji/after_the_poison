# After the Poison - reproducibility package

Tabular Q-learning after finite-budget reward poisoning: epsilon-greedy, softmax and a UCB-style selector. The attacker is an independently reconstructed and adapted FAA (from this paper: https://arxiv.org/pdf/2003.12613), with a documented demotion-sign choice, per-step cap and cumulative budget. 

The saved dissertation figures are in [`publication/figures`](publication/figures). [FIGURE_INDEX.md](FIGURE_INDEX.md) links each figure to its exact data and script. 

## What is included

| Experiment | Included evidence | Status |
|---|---|---|
| Controlled chain, start/reset S2 | Matching source/configuration, raw archive, original report, audit and replay traces | All 3,606 paired records |
| Controlled chain, start/reset S0 | Matching source/configuration, raw archive, original report, audit and replay traces | All 3,606 paired records |
| Terminal theory validation | Source/configuration, raw archive, summary, survival checkpoints | 2,402 completed pairs and 2 explicitly skipped impossible branch requests; all 2,404 jobs accounted for |
| Deterministic UCB count sweep | Source, 32 exact per-condition checkpoints, tables and plots | Complete, including small-gap extension |
| Earlier terminal warm-up | Exported report/summary and plots | 16,016 pairs reported |
| Earlier chain warm-up | Exported report, per-run summary and plots | 1,803 pairs reported |

The two chain audits reanalyse the original chain experiments. Every paired record contains an attacked run and a clean comparison run.


## Install

Use Python 3.10 or newer. From this folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe reproduce.py figures
```

On macOS/Linux, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`. Alternatively activate your environment and use `python` in all commands below. NumPy and Matplotlib are required; a TeX installation is needed only to compile the native TikZ diagram or dissertation.

Outputs are written under `outputs/`. Choose a fresh `--out` directory if a plotting/reanalysis output already exists.

## Four different reproduction tasks

**1. Regenerate figures:**

```powershell
python reproduce.py figures
```

Open `outputs/figure_rebuild/figures/`. To compile the native TikZ Figure 3.1 as well, use `--latex` and a fresh output directory. This requires `pdflatex` on your PATH. 


**2. Rebuild the statistical analysis from the raw records (no new learning simulations, except selected independent replay checks):**

```powershell
python reproduce.py reanalyse
python rebuild_inputs.py --reports outputs/reanalysis --out outputs/reanalysis_inputs
python reproduce.py figures --inputs outputs/reanalysis_inputs --out outputs/reanalysis_figures
```

The first command expands the supplied archives under `outputs/raw/` and runs the original report/audit scripts. 

A figure rebuild using `--inputs` replaces the five chain CSV inputs; terminal and count-sweep inputs remain the supplied reference inputs. To replace terminal inputs too, use the procedure in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).


**3. Run the learning experiments again from scratch:**

```powershell
python reproduce.py rerun --experiment controlled --dry-run
python reproduce.py rerun --experiment controlled
python reproduce.py rerun --experiment start0
python reproduce.py rerun --experiment terminal_validation
```

Use `--resume` after interruption; use `--limit 2` for a small check first. These produce fresh records under `outputs/fresh_simulations/`; they do not replace your supplied records. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for analysing those new outputs. 

The deterministic count calculation is separate and quick:

```powershell
python reproduce.py sweep
```

It searches for exact integer crossing times and skips unchanged waiting periods.

---

Note:

To check the original raw records and selected independent replays, this requires the full ZIP. This is **available upon request**. 

```powershell
python reproduce.py verify --replay
```
Checks all job IDs/settings, original exported arm results, audit expenditure/reward values, reward-change caps and code hashes. Independently replays the lowest-seed C=3 pair in each chain condition: 12 representative pairs. The result is saved to `outputs/record_verification.json`.

