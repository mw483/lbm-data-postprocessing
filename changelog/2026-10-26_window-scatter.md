# Run-to-run spread against window-to-window change (2026-10-26)

**Commits**: `25ca674` (range `50dc6ac..25ca674`, branch `analysis/scalar2-outputs`)

**Goal**: Find out whether the difference between runs `20261011_scalar2` and `20261026_scalar2` is more than the noise of one 200 s averaging window, using only data already on disk.

**Result**: Unit tests pass (26 tests, including the related test files). Smoke run on synthetic `prof*.csv` files (3 runs, 4 windows): all outputs were written. **Not checked**: the script on the real 20261011 and 20261026 data. Mikael runs it on his PC.

## Context

Mikael's request (2026-10-26): the runs `flat_512x128x1024/20261011_scalar2` and `flat_512x128x1024/20261026_scalar2` (before and after the particle SGS MPI fix) show different upper-level `<w'w'>` and `<u'w'>` late in the run (for example the window ending at step 175001, above 100 m). Near the ground they are nearly identical.

What is known:

- `header.txt` is identical between the two runs.
- The job logs differ only in the random initial disturbance seed (`std::random_device`: 841848580 vs 1978407501).
- The professor doubted that seed noise could be this large.

Mikael chose the cheap check ("option 1"): compare the run-to-run difference with the window-to-window change inside each run. The more thorough alternative, a seed ensemble on TSUBAME, was **not done**.

## Commit 25ca674: compare_window_scatter

| File | Change | Why |
|---|---|---|
| [physics_core/window_scatter.py](../physics_core/window_scatter.py) | New. `quantity_table(windows, quantity)`: DataFrame of one quantity, index `z`, one column per step. `between_run_spread(tables)`: max - min over the runs, on the steps and heights every run has (two runs: `abs(a - b)`). `within_run_change(table)`: `abs(Q_k - Q_{k-1})`, labelled by the later step, first window dropped. `layer_mean(table, zband)`: mean over `zband[0] <= z <= zband[1]`, NaN levels skipped. | Pure functions for the two quantities that are compared, kept apart from plotting so they can be tested. |
| [scripts/compare_window_scatter.py](../scripts/compare_window_scatter.py) | New. `--set NAME` (run set from `run_sets.yaml`) and `--step` (window for the profile figure, default the last common one). Quantities: `U`, `var_u`, `var_w`, `cov_uw`, `flux_wt`. Layer for the time series: 100-400 m (`ZBAND`). Profile plots go up to 1000 m (`ZMAX`). Writes to `<figures>/<set>/window_scatter/`: `window_scatter_vs_time.png`, `window_scatter_step<step>.png`, `window_scatter.csv`, `runs.yaml`. | Does the comparison for every run of a set and keeps the outputs per set, like the other comparison scripts ([2026-10-26_run-sets.md](2026-10-26_run-sets.md)). |
| [tests/test_window_scatter.py](../tests/test_window_scatter.py) | New, 4 tests: table is z by step; spread uses common steps and any number of runs; within-run change drops the first window; layer mean limits heights and skips NaN. | Check the arithmetic. |
| [README.md](../README.md) | `compare_window_scatter` added to the list of scripts that take `--set`, and one usage line: `python scripts/compare_window_scatter.py --set flat512_sgsfix`. | Make the script findable. |

No physics or numerics of the solver changed. This is analysis code only.

## How to read the result

- The within-run change is one window's sampling noise plus the slow trend (z_i growth, wind decay). It is therefore an **upper bound** of the noise of one window.
- If the run-to-run spread is about as large as the within-run change, the gap between the runs is compatible with seed noise. If it is clearly larger, the runs differ by more than window noise would explain.
- With more than two runs the spread is a range (max - min), and it grows with the number of runs. Compare it with care; the pairwise check is the clean one.

## Statistic explanation (CLAUDE.md rule)

1. **What it measures**: how far apart the horizontal-mean profiles of the runs are in one window, against how much one run's profile moves from one window to the next.
2. **Why this statistic**: the purpose is a run check. The question is whether a late-time gap in upper-level `<w'w'>` and `<u'w'>` between two runs with identical build parameters exceeds the noise of one averaging window. The within-run change is the cheapest noise estimate from data already on disk. A seed ensemble would be cleaner but needs new runs.
3. **Reference expectation**: no published value for this domain. For orientation only: sampling errors of CBL variances over averages shorter than a few large-eddy times are tens of percent (Lenschow, Mann & Kristensen 1994, J. Atmos. Ocean. Tech. 11, 661-673) [U]. Not checked against the paper.
4. **Units, normalisation and sample**: the quantity's own units (m/s, m^2/s^2, K m/s), no normalisation. Each window is a 200 s mean sampled every `cout_step` = 500 steps (`CFout 500` in `defaults.yaml`), which is 4 s, so about 50 samples per window. Horizontal average over the whole domain (ranks averaged). Layer means over 100-400 m.

## What was deliberately left alone

- No seed ensemble on TSUBAME (the thorough alternative).
- No statistical test and no threshold. The script shows the two sizes next to each other; Mikael judges.
- No run on the real 20261011 and 20261026 data in the cloud.

## How to check

```sh
python -m pytest tests/test_window_scatter.py
python scripts/compare_window_scatter.py --set flat512_sgsfix
python scripts/compare_window_scatter.py --set flat512_sgsfix --step 175001
```

Output is in `<figures>/flat512_sgsfix/window_scatter/`.
