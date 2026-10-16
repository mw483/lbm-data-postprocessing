# Reader for scalar2 solver CSV statistics, inventory and profile scripts (2026-10-16)

**Commits:** `b928177`, `cb29aee` (range `1773e52..HEAD`, branch `analysis/scalar2-outputs`, branched from `analysis/presentation-oct`)
**Goal:** Python analysis of the CSV statistics that Run 3 (LBM-city scalar2, `flat_512x128x1024`, convective, output folder `20261011_output_flat_512x128x1024_scalar2`) writes.
**Result:** `tests/test_lbm_output.py` (11 tests) passes. Both scripts ran on a synthetic 4-rank run folder written in the solver formats, including a two-case comparison. **Nothing was run on real Run 3 data** (the data is on the lab PC / TSUBAME).

---

## Context

Mikael asked for a plan for Python analysis scripts for the new Run 3 statistics and approved it on 2026-10-16. The file formats were read from LBM-city `src/output_user_def.cu` (branch `mikael/cases`, commit `9312d5c`). The full explanation is in the project file `planning/scalar2_outputs_and_analysis_plan_2026-10-16.md` (not part of this repo; not read for this entry).

Format facts the reader relies on (from the brief; the first and the stitching rule are also stated in the module docstring):

- First line of every file: `rank,rank_x,rank_y,rank_z,step,time,xg_min,yg_min,zg_min`. `xg/yg/zg_min` are the global domain minimum, the same on every rank. Stitching therefore uses `rank_x/y/z`.
- Plane labels are one-based global cells. `xz_yav` has no label line. `yz` is ny rows x nz columns. `xy_ag` prints `nan` where another z-rank owns the level.
- Plane values are raw moments (`uu` = <u u>), written with 6 decimals. `prof*.csv` is the per-rank xy mean at `%.15e`, so the profile script uses `prof`.

## Decisions (Mikael)

- Scope: reader + moments module + first two scripts.
- Branch from `analysis/presentation-oct`.
- CSV run folders sit under `D:\lbm_results\`, one folder per run (`wind_outputs: D:/lbm_results`).
- `xy_ag_*` files are skipped for flat runs: the AGL planes repeat the xy planes on flat ground.
- New module `data_loaders/lbm_output.py` instead of extending `lbm_parsers.py`. The old `XYStackedParser` needs `ny_rows` by hand and `XZMatrixParser` breaks on labelled xz/yz files. The old parsers are untouched because existing scripts use them.
- `physics_core/moments.py` does not clip negative variances (`turbulence.py` does), so round-off problems stay visible as NaN sigma or skewness.
- The neutral twin case is in `CASES` as a commented line. Mikael fills in the folder name after it has run.

## Commit `b928177`: reader and central moments

| File | Change | Why |
|---|---|---|
| `data_loaders/lbm_output.py` (new) | `LAYOUTS` table (xz_yav, xy_ag, xy, xz, yz). `read_header_txt`, `read_plane_file`, `scan_run`, `list_steps`, `plane_path`. `load_plane` reads every rank of one variable and step and stitches by `rank_x/y/z` into a `Plane`. `_label_positions` gives cell-centre positions from the one-based labels. `load_prof` reads all `prof<step>_<rank>.csv` into one table. `domain_profile` averages the ranks at each z. | One reader for all layouts that also handles the labelled files. |
| `data_loaders/lbm_output.py:_check_unsplit` | `xz_yav` with ranks split in y raises `NotImplementedError`. | Partial y-averages are not combined. |
| `data_loaders/lbm_output.py:domain_profile` | Plain mean over ranks. | Exact for flat cases with equal ranks, approximate with buildings (stated in the docstring, per the brief). |
| `physics_core/moments.py` (new) | `covariance`, `third_moment`, `mixed_third_moment`, `sigma`, `skewness`, `tke`, `profile_moments`. `sigma` gives NaN for negative variance, `skewness` NaN for variance <= 0. No clipping. | Raw moments to central moments. |
| `tests/test_lbm_output.py` (new) | 11 tests on small files in the solver formats. | Check the reader and moments. |

## Commit `cb29aee`: inventory and per-window profile scripts

| File | Change | Why |
|---|---|---|
| `scripts/inventory_lbm_output.py` (new) | Per case: for each variable, step count, first and last step, min and max rank count against `ncpu` in `header.txt`. Optionally (`CHECK_SHAPES`) loads the newest step of every plane variable and checks the stitched shape against the domain size from the header. Skips `xy_ag_` (`SKIP_PREFIXES`). Writes `inventory_<case>.csv`. | Find missing files before analysis. |
| `scripts/plot_profiles_by_window.py` (new) | Per case, loads each `prof` step, `domain_profile`, `profile_moments`. Plots U, sigma_w, TKE, S_w, theta, w'theta' per 200 s window (darker = later). With more than one case, plots the last common window of all cases together. Writes the per-window table as CSV. `ZMAX = 2048`. | See when profiles stop changing; compare convective and neutral. |
| `plotting_core/profile_plots.py:plot_profile_panels` | New function: one panel per quantity, shared height axis, one line per profile, optional colours and styles. | Used by the profile script. |
| `local_paths.example.yaml` | Comment on `wind_outputs` rewritten; example `D:/lbm_results`. | Document the run-folder layout. |
| `README.md` | New section "Solver statistics, scalar2 and later (2026-10-16)". | How to run the scripts. |

## What was deliberately left alone

- `data_loaders/lbm_parsers.py` and the scripts that use it.
- Files with a plane suffix (`xz_ins_*`, `yz_ins_*`): not read yet. The inventory only counts them in the folder listing.
- `xy_ag_*` for flat runs.

## Not checked and open items

- Not run on real Run 3 data. Real files may differ from the synthetic ones the tests and smoke test use.
- The full pytest suite has 1 failure that exists before these commits: `tests/test_particle_io.py::test_streamed_trajectories_read_11_column_file` (polars `SchemaError`, new_columns 5 != 11). Probably a polars version difference in this environment (inferred, not investigated). Not touched.
- `xz_yav` with ranks split in y is not supported.
- `domain_profile` is approximate for cases with buildings.
- Neutral case folder name is still to be filled in.
- Not verified here: the contents of the planning file and of `output_user_def.cu`; the format facts above come from the brief.

## How to check

```sh
git log --oneline 1773e52..HEAD
git diff -w --stat 1773e52 HEAD
pip install -e .[dev]
pytest tests/test_lbm_output.py
# set wind_outputs: D:/lbm_results in local_paths.yaml
python scripts/inventory_lbm_output.py
python scripts/plot_profiles_by_window.py
```
