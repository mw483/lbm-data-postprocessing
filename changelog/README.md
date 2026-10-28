# Changelog

Notes on what changed in this repo and why. Each file covers one piece of work. Written so you can read it once and understand every change without opening the diffs.

## Index

| Date | File | What it covers | Commits |
|---|---|---|---|
| 2026-10-01 | [2026-10-01_cleanup-structure.md](2026-10-01_cleanup-structure.md) | Branch `cleanup/structure`: hygiene, installable library, archive, particle velocity-unit fix, shared wind and PyVista code, pytest checks | `5f32002` `1b48476` `575d2e8` `c6a3cfc` `20493e6` `2b7e95b` `37411b4` `87262d1` |
| 2026-10-05 | [2026-10-05_ask-dont-assume.md](2026-10-05_ask-dont-assume.md) | CLAUDE.md: new "Ask, don't assume" rule above the workflow steps; no code changed | `ddaee2a` |
| 2026-10-05 | [2026-10-05_presentation-scripts.md](2026-10-05_presentation-scripts.md) | Branch `analysis/presentation-oct`: transit time to first sensor entry (bug fix), raw-count TTDs, per-machine `local_paths.yaml`, Parquet cache, side-by-side live demo for the 2026-10-07 talk | `4fea15c` `588fadb` `3490c20` `af2a382` `53f0b81` |
| 2026-10-06 | [2026-10-06_particle-stats-animation.md](2026-10-06_particle-stats-animation.md) | Branch `analysis/presentation-oct`: particle u, v, w statistics vs height, TTD statistics table, real-time source-to-sensor animation, optional `wind_outputs` path. Not run on real data | `771df9f` `b96f838` `c3bc27d` |
| 2026-10-16 | [2026-10-16_scalar2-output-reader.md](2026-10-16_scalar2-output-reader.md) | Branch `analysis/scalar2-outputs`: reader for the scalar2 solver CSV statistics, central-moments module, inventory script, per-window profile script. Run folders now `<case>/<date>_<tag>` via `lbm_results`. Not run on real data | `b928177` `cb29aee` `e279e5e` |
| 2026-10-16 | [2026-10-16_map-3d-viewer.md](2026-10-16_map-3d-viewer.md) | Branch `analysis/scalar2-outputs`: 3D viewer for map sets (topography, building, vegetation) with face-only building meshes, crop, picking and source overlay; map reader handles touching Fortran values. Run on the Jakarta map in the cloud only, not on the PC. Follow-up: `--case` reads an LBM-city case's map set through the optional `lbm_cases` path | `08fdcab` `6da5fe3` `facb558` `bb53352` |
| 2026-10-19 | [2026-10-19_velocity-stress-and-heatmaps.md](2026-10-19_velocity-stress-and-heatmaps.md) | Branch `analysis/scalar2-outputs`: velocity and Reynolds stress profiles per window (as is and / Ub, Chang et al. 2009 style), y-averaged x-z heatmaps of U, W, sigma_w, TKE with shared colour scale, GIF and MP4. Run on copies of real output in the cloud, not on the lab PC | `0abeba0` `70483dd` `bf0f9a7` |
| 2026-10-19 | [2026-10-19_particle-density-statistics.md](2026-10-19_particle-density-statistics.md) | Branch `analysis/scalar2-outputs`: reader, statistics and script for the C++ particle density outputs (counts to concentration per m^3 per snapshot, C(z), y-mean C(x) with block bands, residence time), convective vs neutral. Run on copies of real output in the cloud, not on the lab PC. Notes a possible rank-boundary jump in near-ground C | `e7260ed` `a50be0f` |
| 2026-10-20 | [2026-10-20_particle-bin-statistics-animation.md](2026-10-20_particle-bin-statistics-animation.md) | Branch `analysis/scalar2-outputs`: reducer for the raw particle binaries (TSUBAME, Python 3.9, numpy), dispersion against particle age, SGS rank-boundary check, `convective_scales` (z_i, w*), particle animations xz / xy / 3d (port of `particle_visual.m`). Tested on synthetic binaries in the cloud only, not on real data or the PC | `b858366` `4a1c79c` `6e5fdb9` |
| 2026-10-21 | [2026-10-21_explain-statistics-rule.md](2026-10-21_explain-statistics-rule.md) | CLAUDE.md: new section "Explaining statistics and figures": every figure or statistic comes with what it measures, why this statistic (purpose of the analysis first), reference expectation with citation ([U] if unchecked), and units, normalisation and sample. No code changed | `47ddbb3` |
| 2026-10-26 | [2026-10-26_run-sets.md](2026-10-26_run-sets.md) | Branch `analysis/scalar2-outputs`: named run sets in `run_sets.yaml`, `--set NAME` on seven comparison scripts, outputs in `<figures>/<set>/<topic>/` with a `runs.yaml` manifest, optional `lbm_reduced` root, 514 figures moved to `figures/flat512_conv_vs_neutral/`, CBL-scaled figure holds all runs. Tested on synthetic data in the cloud for one script; others lint-checked only | `b221977` `e36036e` `e3742d7` `03524d0` |
| 2026-10-26 | [2026-10-26_window-scatter.md](2026-10-26_window-scatter.md) | Branch `analysis/scalar2-outputs`: `compare_window_scatter` compares the run-to-run spread of the `prof*.csv` window means (U, var_u, var_w, cov_uw, flux_wt; layer 100-400 m) with each run's window-to-window change, to judge whether the 20261011 vs 20261026 gap is more than seed noise. Unit tests and synthetic smoke run only, not run on the real data | `25ca674` |
| 2026-10-28 | [2026-10-28_jakarta-map-analysis.md](2026-10-28_jakarta-map-analysis.md) | Branch `analysis/scalar2-outputs`: urban morphology library (lambda_p, H_av, lambda_f, building groups, tiles), map georeference helpers, and `scripts/jakarta-map-analysis/` (consistency checks, location fit against OSM polygons, statistics, figures). Run on the 12 m map in the cloud only, not on the PC. Map matches 2023 OSM buildings (iou 0.75), not the 2017 strip (0.42) | `74e9157` `3a6f2c9` |

## Glossary

| Term | Meaning |
|---|---|
| LBM | Lattice Boltzmann Method, the solver in the LBM-city repo that produces the wind and particle data |
| Lattice units | The solver's internal units. A velocity of 0.02 is one CFL step. Multiply by `c_ref` to get m/s |
| `c_ref` | Velocity scale = `velocity / cfl` from the run argument `-velocity_lbm 2.0 0.02`, so 2.0 / 0.02 = 100 |
| SGS | Sub-grid scale. The turbulent velocity the particle model adds on top of the resolved (grid-scale) velocity |
| Resolved | Velocity interpolated from the LBM grid, without the SGS part |
| `flg_particle` | Solver switch in `Define_user.h`. 1 = Lagrangian stochastic model with SGS (writes `uvw_sgs*.bin`), 2 = resolved only |
| `.bin` files | Raw particle output of the solver: `index`, `position`, `uvw`, `uvw_sgs`, `velocity`, one file per rank group and output step |
| Particle ID | `source x 10000 + release number` |
| Virtual tower | A vertical wind profile read out of the y-averaged XZ plane at one x position |
| Footprint | Map of where particles that reach a sensor came from (source area) |
| Kljun / Schmid | Two analytical footprint models that the LBM footprints are compared with |
| Registry | Planned YAML file per simulation case (paths, dx, sensors, u*, z0). Designed, not implemented |
| Map set | The three map files of one case: `topography.dat`, `building.dat`, `vegetation.dat`. In a map set, building and vegetation heights are absolute (ground + object) |
| Stride | Coarsening factor of the map viewer: one drawn column covers stride x stride cells |
| Window | One 200 s averaging period of the solver statistics; steps like 25001-175001 are the window ends |
| Ub | Inflow (initial) velocity, 5 m/s in the flat runs; used to normalise the profile figures |
| Resolved TKE | 0.5 (var_u + var_v + var_w) from the grid-scale variances, no SGS part |
| Reducer | `scripts/reduce_particle_bins.py`: runs on TSUBAME, turns the raw particle `.bin` files into small `reduced.npz` and snapshot files for the PC |
| Particle age | Time since release, from the release number in the particle ID. Age in outputs x `dt_output` (0.8 s) |
| z_i, w* | Mixed-layer depth (height of minimum total heat flux) and convective velocity scale (g / theta0 x surface flux x z_i)^(1/3) |
| Rank boundary | x = 256, 512, 768 m, where the 4 GPU ranks meet and particles move between ranks over MPI |
| Editable install | `pip install -e .`: Python imports the repo folders directly, so edits take effect without reinstalling |
| Run set | Named group of runs in `run_sets.yaml` (any number, order = colour order) that a comparison script reads with `--set NAME`; outputs go to `<figures>/<set>/<topic>/` |
| Manifest | `runs.yaml` in an output folder: set, runs, data folders read, script, date and repo commit |
| Within-run change | `abs(Q_k - Q_{k-1})` of one run between consecutive windows: one window's sampling noise plus the slow trend, so an upper bound of the noise |
| Between-run spread | Max - min over the runs of a set, per window and height; `abs(a - b)` for two runs |
| lambda_p, lambda_f, H_av | Plan area fraction (built share of ground), frontal area index (wall area facing the wind per ground area), area-weighted mean building height |
| Building group | 4-connected set of building cells; the raster has no building IDs, so touching buildings merge and single cells count |
| Georef | `georef.yaml`: where a map sits on Earth (orientation, offset, scale, CRS) |

## Inspecting the changes

```sh
cd lbm-data-postprocessing
git checkout cleanup/structure

git log --oneline main..cleanup/structure        # the 8 commits
git diff --stat main cleanup/structure           # files changed, whole branch
git diff main cleanup/structure -- data_loaders  # one folder only
git show <hash>                                  # one commit, message and diff
git show --stat <hash>                           # one commit, files only
git log -p main..cleanup/structure -- data_loaders/particle_io.py   # history of one file
git diff main cleanup/structure --find-renames --stat   # renames show up as moves
```
