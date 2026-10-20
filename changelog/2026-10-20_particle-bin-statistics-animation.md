# Raw particle binaries: Lagrangian statistics and animations (2026-10-20)

**Commits:** `b858366`, `4a1c79c`, `6e5fdb9` (range `b6e2f4f..HEAD`, branch `analysis/scalar2-outputs`)
**Goal:** Show all particles of the two flat runs as an animation (port of Mikael's MATLAB `particle_visual.m`) and add particle analyses: dispersion against particle age, and a check of the SGS velocity at the GPU rank boundaries. Mikael has a presentation on 2026-10-21, so no new simulations; only existing data.
**Result:** A reducer for TSUBAME, a statistics module, a plot script and an animation script. pytest `tests/test_particle_bin_stats.py` (4 tests) plus `tests/test_particle_density.py`: 12 passed. The whole chain ran end to end in the cloud on **synthetic** binaries in the solver's file format (4 x-ranks, random walk, SGS deliberately reset at each rank crossing): reducer, plot script, and the three animation modes including PyVista 3D off-screen. In that test the synthetic SGS reset showed up as dips at 256, 512 and 768 m. **Not run on the real TSUBAME data and not run on Mikael's PC.**

---

## Context

Mikael asked for (a) a visualisation of all particles, with the modes of the old MATLAB script (3D scatter animation, XZ and XY plane modes, black background), and (b) more particle analyses. The wind statistics are handled by the professor, so they are not part of this work. Mikael approved this order: animation first, then dispersion against particle age and the SGS rank-boundary check. A two-pass sensor analysis was to be done only if time was left. It was not done.

The raw particle `.bin` files stay on TSUBAME. Mikael can run an interactive TSUBAME node with Python 3.9, or copy files down with rclone. So the work is split in two:

- The reducer runs on TSUBAME next to the data. It needs only Python 3.9 and numpy (checked with `vermin`: minimum Python 3.6).
- The plot and animation scripts run on the PC from the small reduced files.

Particle ID decoding was checked in LBM-city `src/Generate_Particle_GPU.cu:93`. `pos_id` is the source label from `particle_position.txt` column 8 (`k * 10000 + 1`), plus the releases since `pstart`. So:

- source line `k = id // 10000`
- release `n = id % 10000 - 1`
- release output = `release_start + n * release_every`, so the age at output `m` is `m - (release_start + n * release_every)`

The rank-boundary check tests the suspicion from 2026-10-19 that the particle MPI type (LBM-city `src/ParamParticle_MPI.cu:165`, `num_ppos = 6`) does not carry `u/v/w_sgs`. If so, the SGS velocity is lost at x = 256, 512 and 768 m. This follows up the "Known issue seen in the results" in [2026-10-19_particle-density-statistics.md](2026-10-19_particle-density-statistics.md). The check measures; it does not prove the cause.

## Commit `b858366`: reducer for the raw particle binaries

| File | Change | Why |
|---|---|---|
| [scripts/reduce_particle_bins.py](../scripts/reduce_particle_bins.py) | New. Streams outputs `--first 1200` to `--last 1800` once. Reads `index` and `position` at every output, and `uvw`, `uvw_sgs` every `--vel-stride 5` outputs. Writes `reduced.npz` and `snapshots/snap_<n>.npz` into `--out` | Raw files are large and on TSUBAME. The reduced files are small enough to copy to the PC |
| [physics_core/particle_bin_stats.py](../physics_core/particle_bin_stats.py) `decode_ids`, `age_in_outputs` | ID to source line and release number; age in outputs | Decoding rule above |
| `:sample_mask` | Keeps a particle when a multiplicative hash of its ID is below the fraction (Knuth constant 2654435761, modulo 2^32). Default fraction 0.125 (1/8) | The same particles appear in every frame. The hash spreads neighbouring IDs, so the subset is not striped by source or release |
| `:new_age_acc`, `add_age`, `age_stats`, `age_histograms` | Per age bin: count, sums of z, z^2, dx, dx^2 (dx = x - x of source), and 2D histograms age x z and age x dx | Dispersion (mean, sigma) and PDF of height against age |
| `:new_height_acc`, `add_height`, `height_stats` | Per 2 m height bin: moments of u, v, w (total) and of the SGS part, plus u w covariance of the total | Particle sigma_w and mean u against height |
| `:new_x_acc`, `add_x`, `x_stats` | Per 2 m x bin, only particles below `--sgs-ztop` (10 m): count, SGS energy, rms of w_s, fraction with SGS velocity exactly 0, mean height | The rank-boundary check |
| `:save_reduced`, `load_reduced`, `read_sources` | One `.npz` with a JSON `meta` entry; reader for `particle_position.txt` | Small, portable files |
| [data_loaders/local_paths.py](../data_loaders/local_paths.py) `particle_reduced_dir` | New helper, returns `<lbm_results>/<run>/particle_reduced` | Same pattern as `particle_postprocess_dir` |
| [tests/test_particle_bin_stats.py](../tests/test_particle_bin_stats.py) | 4 tests: ID decoding and age, fixed hash subset near the fraction, age accumulator, height and x accumulators with a save/load round trip | Check the formulas |

Reducer defaults (all are command-line options): `--release-start 1200`, `--release-every 1`, `--dt-output 0.8`, `--c-ref 250.0`, `--dx 2.0`, `--lx 1024`, `--lz 2048`, `--max-age 600` outputs, `--snap-every 5`, `--snap-fraction 0.125`.

Age statistics only use sources with x <= 104 m (`--upstream-xmax 104`). Reason: particles from sources further downstream would leave the domain through the outflow at x = 1024 m within the plotted ages. Only the survivors would remain at large age, which biases the statistics (survivor bias).

## Commit `4a1c79c`: statistics script, figures, convective scales

| File | Change | Why |
|---|---|---|
| [scripts/plot_particle_bin_stats.py](../scripts/plot_particle_bin_stats.py) | New. Reads `particle_reduced/reduced.npz` of both runs plus the solver profile at step `PROF_STEP = 175001`. Writes to `<figures>/particle_bins/`: `dispersion_vs_age.png`, `dispersion_vs_age_cbl.png`, `z_pdf_vs_age.png`, `velocity_profiles.png`, `sgs_along_x.png` and CSVs `dispersion_vs_age.csv`, `velocity_profiles.csv`, `sgs_along_x.csv` | Analyses Mikael approved |
| [plotting_core/particle_bin_plots.py](../plotting_core/particle_bin_plots.py) | New: `plot_lines_grid` (line panels, dotted vertical lines for rank edges), `plot_age_pdf` (PDF of height per age, log colour scale shared by the cases), `plot_profiles` (profiles against height) | Figures for the script |
| [physics_core/moments.py](../physics_core/moments.py) `convective_scales` | New function, see the box below | z_i and w* for the scaled dispersion plot |

Script settings: `MIN_COUNT = 2000` (age bins and height bins with fewer samples are not plotted), `RANK_EDGES = (256, 512, 768)`, `THETA0 = 300`, `ZMAX_PDF = 500`, `ZMAX_PROFILE = 500`.

What the figures show:

- `dispersion_vs_age.png`: mean height, sigma_z, mean downwind travel, sigma_x against particle age.
- `dispersion_vs_age_cbl.png`: convective case only, z / z_i against t w* / z_i. Not drawn when w* is NaN (neutral).
- `z_pdf_vs_age.png`: PDF of height at each age, mean height in white.
- `velocity_profiles.png`: particle sigma_w (total and SGS part) and mean u against the Eulerian resolved profiles.
- `sgs_along_x.png`: for particles below 10 m, SGS energy, fraction with zero SGS velocity, mean height and sample count along x, with the rank boundaries dotted. A drop in SGS energy and a rise in the zero fraction at 256, 512 and 768 m would support the suspicion. A change in mean height tells whether a jump is a height effect instead.

**New calculation: `convective_scales(moments, theta0=300.0, g=9.81)`** (new function, no existing result changes)

- Total heat flux = resolved `flux_wt` + model `flux_wt_model`.
- z_i = height of the minimum of the total heat flux.
- Surface flux = value at the first nonzero level (levels below the ground are zero).
- w* = (g / theta0 * surface flux * z_i)^(1/3), with theta0 = 300 K (header `out_ref`).
- Returns `(z_i, w*, surface flux)`. z_i and w* are NaN when the surface flux is not positive, so the neutral run gives NaN.
- On the convective run's profile step 175001: flux 0.115 K m/s, z_i 355 m, w* 1.10 m/s.
- To undo: remove the function. Nothing else in the repo calls it except the new plot script.

## Commit `6e5fdb9`: particle animations

| File | Change | Why |
|---|---|---|
| [scripts/animate_particles.py](../scripts/animate_particles.py) | New. Port of `particle_visual.m` with three modes: `--mode xz` (side view, all particles projected, or a y slab with `--slab`), `--mode xy` (top view, or a z slab), `--mode 3d` (PyVista point cloud, off-screen, one row per case). Black background (`BACKGROUND = "black"`), colour by particle age or by height (`--color age/z`), one colour scale for all frames and both cases. Writes `frame_<n>.png`, `animation.gif` and `animation.mp4` | Mikael's request to visualise all particles |
| [README.md](../README.md) | New section "Raw particle binaries: Lagrangian statistics and animations (2026-10-20)" with the run commands | How to run |

Other options: `--zmax 300`, `--every n`, `--vmax`. Settings: `FPS = 10`, `POINT_SIZE = 0.4`, `CMAP = "turbo"`, `DOMAIN = (1024, 256)`. The default colour maximum is taken from the last snapshot. The two cases are stacked in one picture so they can be compared. GIF and MP4 reuse `frames_to_gif` and `frames_to_mp4` from `plotting_core/heatmap_plots.py`.

## What was deliberately left alone

- Sensor two-pass analysis (only if time was left; it was not).
- Residence or exit-time distribution.
- Per-ID trajectories.
- Wind statistics (handled by the professor).
- No solver (LBM-city) changes, including `ParamParticle_MPI.cu`.

## Open items and limits

- **Not run on real data.** The first run on TSUBAME is the real test of the reducer. The first PC run is the real test of the plot and animation scripts and of `--mode 3d`.
- The rank-boundary result is a measurement. If the SGS energy dips at 256, 512 and 768 m, that supports the MPI-type suspicion but does not prove it.
- Snapshots keep 1/8 of the particles. Particle counts in the animation are not the true counts. The panel title shows the number drawn.
- `--c-ref` defaults to 250.0 because the flat_512x128x1024 runs use `velocity_lbm: [5.0, 0.02]` (c_ref = 5.0 / 0.02 = 250, also `c_ref` in the runs' header.txt). The glossary's 100 is the old repo 1 runs (`2.0 0.02`). Pass `--c-ref` for other cases, because it scales every velocity.
- Snapshot-only vs full statistics: velocity moments and the x check use every 5th output only (`--vel-stride 5`).
- The `animate_particles.py` docstring said output goes to `<figures>/particle_animation/<mode>/`; the code uses `<mode>[_slab<lo>-<hi>]_<color>` (e.g. `xz_age`). The docstring was corrected together with this entry.

## How to check

```sh
python -m pytest tests/test_particle_bin_stats.py tests/test_particle_density.py     # 12 passed

# On TSUBAME (Python 3.9, numpy)
python3 scripts/reduce_particle_bins.py --bin-dir <particle folder> \
    --sources <LBM-city>/cases/flat_512x128x1024/particle_position/particle_position.txt \
    --out <somewhere>/particle_reduced

# On the PC, after copying particle_reduced to <lbm_results>/<case>/<date>_<tag>/particle_reduced
python scripts/plot_particle_bin_stats.py
python scripts/animate_particles.py --mode xz
python scripts/animate_particles.py --mode xy --slab 0 10
python scripts/animate_particles.py --mode 3d

git log --oneline b6e2f4f..HEAD
git diff --stat b6e2f4f HEAD
```
