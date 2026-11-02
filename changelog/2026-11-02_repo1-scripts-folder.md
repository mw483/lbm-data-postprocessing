# Repo 1 scripts moved to scripts/repo1_runs/ (2026-11-02)

**Commits**: `23ff4bb`, `4425351` (range `7c1a231..4425351`, branch `analysis/scalar2-outputs`)

**Goal**: `scripts/` had become crowded. Mikael asked to separate the scripts for the older repo 1 runs from the scripts for the LBM-city scalar2 convective runs.

**Result**: Tested without real data.
- All 31 moved scripts pass `py_compile`.
- Their package imports resolve from outside the repo after `pip install -e .`.
- `pytest`: 104 passed, 2 failed. The same 2 fail before the change: `test_particle_io::test_streamed_trajectories_read_11_column_file` (polars 2.0) and `test_urban_morphology` (missing module `affine`).
- The scripts themselves were **not run**. Their data is on the lab drives.

## How the cut was chosen

- Date each script was first added (from git history): 31 scripts were added between 2026-06-01 and 2026-10-06. All of them read repo 1 runs: `20260527` flat_3072, `20260612` cube_3072, `20260630` flat_16mapproach, `20260707` shortroughness, `20260803` cube_16mapproach.
- No script was added between 2026-10-06 and 2026-10-16.
- The 14 scripts from 2026-10-16 on stay in `scripts/`. The first scalar2 script is `cb29aee` (see [2026-10-16_scalar2-output-reader.md](2026-10-16_scalar2-output-reader.md)). Mikael agreed to cut at 2026-10-16.
- Each script was put in a category by its imports and input data. Mikael first suggested four: sensor 3D vis, basic statistics, transport time, source area. He accepted these corrections:
  - Sensor data is shared by the 3D views and the transit-time scripts, so there are two folders, `sensor_3d/` and `sensor_transit_time/`.
  - `plot_density_dvr` and `plot_density_isosurfaces` show the whole-domain density, not a sensor. They stay in `sensor_3d/`.
  - `extract_variance`, `extract_sourcearea_wind_stats`, `plot_meteorological_profiles` and `analyze_effective_velocity` produce the inputs of the Kljun/Schmid models, so they are in `source_area/`.
  - `demo_presentation` goes in `sensor_3d/` (Mikael's choice).

## Commit 23ff4bb: move the 31 scripts

Pure `git mv` renames (git reports R100, 0 insertions, 0 deletions). `git log --follow <new path>` keeps the history of each script. Old path was `scripts/<name>.py`.

| New folder | Scripts |
|---|---|
| `scripts/repo1_runs/sensor_3d/` | `animate_particles_to_sensor`, `demo_presentation`, `plot_density_dvr`, `plot_density_isosurfaces`, `plot_particle_trajectory`, `plot_particle_velocity_profiles`, `plot_sensor_density_cloud`, `plot_sensor_density_isosurfaces`, `plot_velocity_particles` |
| `scripts/repo1_runs/sensor_transit_time/` | `plot_ensemble_ttd`, `plot_transit_times`, `table_transit_time_stats` |
| `scripts/repo1_runs/basic_statistics/` | `analyze_inflow_statistics`, `analyze_particle_statistics`, `calculate_plume_dispersion`, `plot_lateral_variance_scatter` |
| `scripts/repo1_runs/source_area/` | `analyze_effective_velocity`, `compare_kljun_lbm`, `compare_lbm_cases`, `compare_schmid_lbm`, `extract_sourcearea_wind_stats`, `extract_variance`, `plot_absolute_line_footprint`, `plot_blending_height`, `plot_footprint_metrics`, `plot_lbm_contours`, `plot_lbm_footprint`, `plot_meteorological_profiles`, `plot_spanwise_footprints`, `plot_vertical_detection`, `visualize_domain` |

Why: see the section above. Why a separate commit with no content change: so the renames are traceable and the path fixes in the next commit are easy to review.

## Commit 4425351: paths from the repo root, README

Mikael asked to fix the relative output paths and the README after the move.

The problem: many scripts built output and parameter paths as `'../figures'` or `'../physics_core/metrics'`. These are relative to the working directory, so they assumed you run the script from inside `scripts/`. Two spanwise scripts were relative to their own folder (`script_dir`). One script, `plot_density_isosurfaces`, used `'./figures'`. These paths now start from `REPO_ROOT` (`data_loaders.local_paths`), so the outputs land in the same folders as before, wherever the script is run from.

| File | Change | Why |
|---|---|---|
| 19 scripts: `sensor_3d/` `plot_density_dvr`, `plot_density_isosurfaces`, `plot_particle_trajectory`, `plot_sensor_density_cloud`; `source_area/` `analyze_effective_velocity`, `compare_kljun_lbm`, `compare_lbm_cases`, `compare_schmid_lbm`, `extract_sourcearea_wind_stats`, `extract_variance`, `plot_absolute_line_footprint`, `plot_blending_height`, `plot_footprint_metrics`, `plot_lbm_contours`, `plot_lbm_footprint`, `plot_meteorological_profiles`, `plot_spanwise_footprints`, `plot_vertical_detection`, `visualize_domain` | New import `from data_loaders.local_paths import REPO_ROOT`. Paths built from it. Example (`compare_kljun_lbm.py`): `params_path = r"../physics_core/metrics/cube_params.json"` became `str(REPO_ROOT / "physics_core/metrics/cube_params.json")`; `output_dir = rf"../figures/flat_domain/..."` became `str(REPO_ROOT / f"figures/flat_domain/...")`. In `plot_density_isosurfaces.py`, `"./figures"` became `str(REPO_ROOT / "figures")` | Scripts no longer depend on the working directory. Output folders are unchanged |
| `source_area/plot_spanwise_footprints.py`, `source_area/plot_absolute_line_footprint.py` | Removed the unused `script_dir` / `python_root` variables (in the second script `script_dir`, which only fed the path). `figure_output_dir` is now `str(REPO_ROOT / "figures/spanwise_analysis/flat_shortroughness/height20")`; `repo_root` in the second script gets the same value | These two used the script folder as base. The old paths went one folder up from `scripts/`, so the new ones give the same target |
| `scripts/repo1_runs/README.md` (new) | Lists the four folders, the runs they read, the scripts per folder, the known state (footprint code on hold, `schmid_params.json` missing) and the library modules only these scripts use | So a reader knows what the folder is and why the library packages were not split |
| `README.md` | Layout table: `scripts/` row says the scalar2 scripts sit directly in `scripts/`; new row for `scripts/repo1_runs/`. `demo_presentation` commands now `python scripts/repo1_runs/sensor_3d/demo_presentation.py`. `analyze_particle_statistics` command now `python scripts/repo1_runs/basic_statistics/analyze_particle_statistics.py   # repo 1 runs` | Paths in the docs must match the new places |
| `pyproject.toml` | Comment on the `video` extra: `scripts/demo_presentation.py` became `scripts/repo1_runs/sensor_3d/demo_presentation.py` | Same reason. Comment only |

No other code change.

Old and new behaviour, and how to revert: output and parameter paths are the same folders as before when the script was run from inside `scripts/`. If a script was run from another folder before, it wrote to a folder relative to that one; it no longer does. To revert, `git revert 4425351` (and `23ff4bb` to move the scripts back).

## What was deliberately left alone

- Footprint code is on hold and was not fixed. `schmid_params.json` is still missing, so scripts that read it still fail (noted in `scripts/repo1_runs/README.md`).
- Library packages (`data_loaders`, `physics_core`, `plotting_core`) were not split by repo. Several modules are used by both sets of scripts: `particle_bin`, `map_io`, `pyvista_helpers`, `local_paths`, `profile_plots`.
- Grouping of the current scalar2 scripts in `scripts/` is deferred ("later", per Mikael).
- The `sys.path` hack in `reduce_particle_bins` is untouched.

## How to check

```sh
pip install -e .
git show --stat -M 23ff4bb                       # 31 renames, 0 insertions, 0 deletions
git log --follow --oneline scripts/repo1_runs/source_area/compare_kljun_lbm.py
git show -w 4425351 -- scripts                   # the path changes
python -m py_compile scripts/repo1_runs/*/*.py
pytest                                           # 104 pass, 2 known failures
```
