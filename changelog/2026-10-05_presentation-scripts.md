# 2026-10-05: Presentation scripts for the 2026-10-07 progress talk

Branch `analysis/presentation-oct` (new, made from `cleanup/structure`). Commits: `4fea15c`, `588fadb`, `3490c20`, `af2a382`, `53f0b81` (range `3055311..53f0b81`).

## Context

On 2026-10-05 the owner (kaka) asked to improve the repo 2 scripts for the progress talk on 2026-10-07. The talk shows, in this order, isopleths, velocity lines, then transit-time distributions (TTDs), live in PyVista, from the lab PC or the laptop.

Three things drove the work:

- The professor asked for TTDs in raw counts, not probability density.
- A bug in the transit-time code (below) made the old TTDs measure the wrong interval.
- The scripts had `D:\` and `C:\` paths written in, so they only ran on the lab PC, and each script re-read the ~600 MB `target_trajectories.csv`. Over the rclone mount on the laptop that is slow.

## Decisions

- Raw counts for both TTD plots (single sensor and spanwise ensemble). Approved by kaka. `density=True` is kept as an option and gives the old PDF.
- The transit-time bug is fixed (approved). Cause: `compute_transit_times` took each particle's last record in `target_trajectories.csv` as the arrival. The C++ suite (repo 1, `Particle_PostProcessing_CPP/src/sensor_density.cpp`, `stream_trajectories`) writes every step of a hit particle, also after it passed the sensor. So the old TTD measured release to leaving the domain or the window end. The arrival is now the first step inside the sensor box, using the same inclusive centre +/- size/2 test as `harvest_ids` in the C++ (checked in repo 1 `sensor_density.cpp`: `harvest_ids` lines 93-122, `stream_trajectories` line 391).
- N in the TTD legend is one particle per source per sensor, because `harvest_ids` flags the first particle per source and sensor (`if (source_hit_sensor[...]) continue;` in `harvest_ids`). The ensemble script keeps one value per particle (its earliest arrival on the spanwise line), so N is the same as before.
- `dt_output` stays 1 s. kaka confirmed the particle `.bin` outputs are 1 s apart.
- The release step is the particle's first record in the CSV. This is valid because these runs released particles from `pstart = FILE_START = 1200` (repo 1 `config_tsubame.py`). Not verified against the real data files.
- Paths come from a per-machine, git-ignored `local_paths.yaml`, so the laptop can point at the rclone mount of TSUBAME `/gs/bs/tga-lbmcity/mikael/LBM_particle_test/Particle_PostProcess_Outputs`. `pyyaml` was added because YAML is the format kaka chose for the case registry.
- Parquet cache of each sensor's trajectories, because every script re-read the whole CSV.
- The demo has a `--record` mode (MP4 orbit plus PNG per stage) as a recorded fallback for the live demo. kaka asked for this.
- Left out on purpose: footprint-model code is untouched (on hold).

## Commit 4fea15c: transit time to first sensor entry, raw-count TTDs

| File:function | What changed | Why |
|---|---|---|
| `physics_core/particle_analysis.py:compute_transit_times` | Rewritten. Signature is now `(trajectories, hits, sensor_size, dt_output)`; takes a path, LazyFrame or DataFrame plus a hit table. Returns a DataFrame `sensor_id, id, step_release, step_arrival, delta_t`, one row per (sensor, particle) hit. Release = min step per particle; arrival = min step where (x, y, z) is inside centre +/- size/2 (inclusive). Hits with no in-box record are dropped with a warning. | Fixes the last-record bug. Callers of the old signature (`csv_path`, `target_ids`, `separator`) are changed in the same commit. |
| `physics_core/particle_analysis.py:scan_trajectories` | New. Lazy scan of the headerless 5 or 11 column CSV with named columns (`TRAJECTORY_COLUMNS`). | Shared by the transit-time code. |
| `data_loaders/particle_io.py:load_hit_table` | New. Reads `sensor_hit_ids.txt` as a table: `sensor_id, sx, sy, sz, source_id, id`. | The arrival test needs the sensor centre per hit. |
| `plotting_core/velocity_analysis_plots.py:plot_transit_time_distribution`, `plot_normalized_ttd_comparison` | New argument `density=False`. Y label becomes "Particles per ... bin"; integer y ticks. `density=True` keeps the old PDF and label. | Professor's request for raw counts. |
| `scripts/plot_transit_times.py` | Uses `load_hit_table` and the new `compute_transit_times`; adds `sensor_size = (8, 8, 8)`; skips a run if the capsule file is missing or has no hits; passes `density=False`. | Follows the new API. |
| `scripts/plot_ensemble_ttd.py` | Hits filtered to the spanwise line (x within 0.5 of `sensor_x`, z within 0.5 of the height); one value per particle via `group_by("id")` and minimum `delta_t`; passes `density=False`. | Same N as before, correct arrival time. |
| `tests/test_transit_times.py` | New. Two tests: arrival is the first in-box step, not the last record (including a particle on the box face); `dt_output` scaling and dropped unreached hits. | Cover the fix. |

## Commit 588fadb: per-machine `local_paths.yaml`

| File:function | What changed | Why |
|---|---|---|
| `data_loaders/local_paths.py:load_local_paths`, `sensor_output_dir` | New. Reads `particle_outputs`, `maps`, `cache`, `figures` from `local_paths.yaml` in the repo root (or the file named by env var `LBM_LOCAL_PATHS`). Relative entries are taken from the repo root. Missing file or key raises an error that says what to do. | One code path for lab PC and laptop. |
| `local_paths.example.yaml` | New template (lab PC and laptop examples in comments). | Starting point per machine. |
| `.gitignore` | Adds `local_paths.yaml` and `cache/`. | Per-machine files stay out of git. |
| `scripts/plot_transit_times.py`, `plot_ensemble_ttd.py`, `plot_sensor_density_isosurfaces.py`, `plot_velocity_particles.py` | Read folders from the settings instead of fixed `D:\`/`C:\` paths. The two 3D scripts now name the run and map file at the top. Figures go to the `figures` folder instead of a cwd-relative `../figures`. The ensemble script's `prof_path` (`Z:\`, used only for advective scaling) is unchanged. | Run on either machine. |
| `pyproject.toml`, `requirements.txt` | Add `pyyaml`. | YAML parsing. |
| `README.md` | Setup step for `local_paths.yaml`. | Documentation. |
| `tests/test_local_paths.py` | New. Example file loads and relative paths resolve from the repo root; a missing key is reported. | Cover the loader. |

## Commit 3490c20: reusable 3D scene builders

| File:function | What changed | Why |
|---|---|---|
| `plotting_core/particle_3d_plots.py:add_density_isopleths` | New. Body of the old isopleth plot, drawing into the active renderer of a given plotter. Optional `bar_title`. Returns False when nothing is drawn. | Two cases in one window, side by side. |
| `plotting_core/particle_3d_plots.py:add_particles_with_velocity` | New. Same split for the velocity plot. Optional `clim` and `bar_title`. Returns the number of points drawn (0 = nothing). | As above; `clim` gives one colour range for both cases. |
| `plotting_core/particle_3d_plots.py:velocity_scalars` | New. Holds the scalar and colormap choice that was inside `plot_particles_with_velocity`. | Needed by the builder. |
| `plotting_core/particle_3d_plots.py:plot_density_isopleths_with_sensor`, `plot_particles_with_velocity` | Same signatures. They now create the plotter, call the builder, bind the `s` screenshot key and show the window. | Existing scripts keep working. Behaviour unchanged is the commit's claim; no pixel comparison was done. |

## Commit af2a382: Parquet cache per sensor

| File:function | What changed | Why |
|---|---|---|
| `data_loaders/sensor_cache.py:load_sensor_subset` | New. First call per (run, sensor) reads the CSV once through `load_trajectories_with_velocities` (velocities in m/s via `c_ref`, default 100) and writes `sensor_<id>.parquet` under the cache folder; later calls read the Parquet file. `rebuild=True` forces a re-read. Returns the trajectory frame and that sensor's hit table. | Avoid re-reading ~600 MB per script, mainly over rclone. |
| `data_loaders/sensor_cache.py:sensor_cache_path`, `trajectories_from_frame` | New helpers: cache file path; frame to `{id: (n, 3) xyz array}` for the isopleth builder. | Support the cache and the demo. |
| `tests/test_particle_io.py` | New test: the cache is built once and the second call works with the CSV deleted. | Cover the cache. |

## Commit 53f0b81: side-by-side live demo

| File:function | What changed | Why |
|---|---|---|
| `scripts/demo_presentation.py` | New. Flat vs cube array for sensor 4 (3672, 256, 90), in talk order: isopleths, velocity lines coloured by w (one shared colour range, 2-98 % of the values), TTD in raw counts. The two 3D views share one camera (`link_views`). Options: `--stage`, `--only`, `--record`, `--rebuild-cache`. `--record` writes an orbit MP4 and a PNG per stage, no windows. Settings are constants at the top of the file. | Live demo plus a recorded backup. |
| `pyproject.toml` | New optional extra `video = ["imageio", "imageio-ffmpeg"]`. | MP4 export for `--record`. |
| `README.md` | Section "Presentation demo (2026-10-07)" with the commands. | Documentation. |

## How it was checked

- 22 pytest tests pass (new: transit-time tests, local-paths tests, cache test).
- Demo `--record` mode ran on synthetic data (two fake runs, 300 hit particles each, a flat and a cube map) under Xvfb. Both 3D stages rendered side by side with the shared camera, a frame from the orbit MP4 was inspected, and the TTD PNG was written.
- The C++ behaviour the fix relies on was read in repo 1 `Particle_PostProcessing_CPP/src/sensor_density.cpp` (`harvest_ids`, `stream_trajectories`) and `calculation.cpp` (both are called on the same positions).
- This entry was checked against `git diff 3055311..53f0b81` and the commit messages.

## Not checked

- Nothing has been run on the real `20260630` and `20260803` outputs yet (the data is on kaka's PC). The real TTD numbers, and the release-step assumption, are untested on real data.
- The interactive (non-record) window path of the demo was not opened (no display).
- The C++ suite was read, not run.

## Open items and known limits

- Release step = first record in the CSV. If particles were released before the post-processed window in another run, delta_t is too short.
- `dt_output = 1.0` is a constant in each script, not read from the data.
- The sensor size `(8, 8, 8)` is hard-coded in the scripts and must match the C++ run (`sensor_8x8x8`).
- Cached Parquet files do not notice changed C++ outputs; use `--rebuild-cache` or `rebuild=True`.
- `C_REF = 100.0` in the demo applies to the 16 m approach runs only.
- `extract_hit_list_by_plane` in `particle_io.py` is no longer used by any script; `extract_hit_list_from_time_capsule` is still used by `plot_particle_trajectory.py`. Both are kept.
- Footprint-model code is untouched (on hold).

## How to see the change

```sh
git log --oneline 3055311..53f0b81
git diff --stat 3055311 53f0b81
git diff -w 3055311 53f0b81 -- physics_core/particle_analysis.py
git show 4fea15c
git show 53f0b81 --stat
```
