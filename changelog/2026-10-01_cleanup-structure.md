# 2026-10-01: Repo cleanup (branch `cleanup/structure`)

8 commits on top of `main`. Nothing was merged, pushed or committed outside this branch. Footprint-model code was not touched (on hold, see Decisions).

Commits, oldest first:

| # | Hash | Subject |
|---|---|---|
| 1 | `5f32002` | Ignore Python cache files and stop tracking `__pycache__` |
| 2 | `1b48476` | Make the library installable and drop sys.path hacks |
| 3 | `575d2e8` | Archive retired scripts and unused library code |
| 4 | `c6a3cfc` | Fix particle velocity units and SGS double count; add raw .bin reader |
| 5 | `20493e6` | Add XZ wind loader and virtual-tower helper; use them in wind scripts |
| 6 | `2b7e95b` | Add pytest checks for the loaders and wind helpers |
| 7 | `37411b4` | Remove leftover sys.path comments |
| 8 | `87262d1` | Share PyVista scene helpers; fix density-mode scaling and DVR max |

Overall: 82 files changed, 995 insertions, 889 deletions (`git diff --stat main cleanup/structure`). Most of the file count is the 26 deleted `.pyc` files and the one-line `sys.path` removals.

## Context

The scripts were written one at a time over several months, each one solving the question of that week. By now the repo had 31 scripts plus 4 library packages, about 7,800 lines of Python. A review on 2026-10-01 (`planning/repo2_review_2026-10-01.md`) found:

- **No dependency list.** No `requirements.txt`, no `pyproject.toml`, no `.gitignore`. The Python and numpy versions were only implied (`np.trapezoid` needs numpy 2).
- **Committed `__pycache__`.** 26 `.pyc` files were in git. 4 of them belonged to modules that no longer exist.
- **Figures are 73 MB of the 78 MB repo** (372 tracked files under `figures/`).
- **Every script did `sys.path.append("..")`** and had to be run from inside `scripts/`.
- **Six scripts fail.** Five of them (plus `extract_variance`) still read `schmid_params.json`, which was renamed to `default_flat_params.json` on 07-10. `plot_spanwise_footprints` calls a plotting function whose arguments have since changed.
- **Copy-pasted code.** The virtual-tower readout was copied in 5 scripts. The PyVista screenshot, sensor box and ground-plane code was copied 3 to 8 times. The footprint pipeline is copied in 6 scripts with two different smoothing formulas.
- **Wrong numbers.** The most important: the particle velocity units (own section below). The review also listed footprint bugs; those are on hold.

The review proposed options A to G. You approved some, chose between others, and put the footprint code on hold. That is the next section.

## Decisions the owner made

These are your decisions, recorded so the reasoning stays attached to the code.

| Option | Decision | Status |
|---|---|---|
| A. Hygiene (`.gitignore`, dependency list, installable packages, `archive/`) | Approved | Done (commits 1, 2, 3) |
| B. One case registry instead of constants in every script | Chose YAML. Design in `planning/case_registry_design_2026-10-01.md` | **Not implemented.** Design only |
| C. Move copy-pasted code into the library | Approved | Partly done: virtual tower, `.bin` reader, PyVista helpers. Footprint pipeline not done (on hold) |
| D. Script layout | D1: one short script per figure type. You may want comparison subplots later, which is easier with separate small scripts | Followed. No scripts were merged in this branch |
| E. Figures out of git | Not done yet. You want figures reachable from home, so the plan is a `figures_root` setting pointing into a cloud-synced folder. Existing figures stay in git for now | Open |
| F. pytest checks | Approved | Done (commit 6) |
| G. LBM-city C++ side | Later, separate thread | Not touched |

Other decisions:

- **Footprint-model code is on hold and was deliberately not touched.** That covers the Kljun and Schmid comparisons, the contour and metrics scripts and the blending height. So its known bugs are listed under Open items, not fixed. Fixing them now would change results you may still be reasoning about.
- **σv sensitivity tests are no longer needed.** `test_arbitrary_sigmav.py` and `test_sigmav_sensitivity.py` were archived.
- **Takamatsu XY scripts are no longer needed.** `plot_xy_heatmap.py` and `plot_xy_vectorfield.py` were archived.
- **Blending height was a dead end but is kept.** `plot_blending_height.py` stays in `scripts/`.

## Commit 1: `5f32002` Ignore Python cache files

| File | Change |
|---|---|
| `.gitignore` | New. Ignores `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.pytest_cache/`, `build/`, `dist/`, virtual environments (`.venv/`, `venv/`), editor and OS files (`.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`, `desktop.ini`) and Office lock files (`~$*`) |
| 26 `__pycache__/*.pyc` files in `data_loaders/`, `physics_core/`, `plotting_core/` | Removed from git (the files stay on your disk until Python rewrites them, and are now ignored) |

**Why.** `.pyc` files are rebuilt automatically by Python. Committing them adds noise to every diff and can conflict between machines and Python versions. 4 of the 26 (`trajectory_io`, `wind_parser`, `trajectory_3d`, `spanwise_plots`) belonged to modules that no longer exist.

**Not ignored.** `figures/` is not in `.gitignore`. That is option E and is still open.

**Checked.** `git ls-files '*.pyc'` lists nothing on the branch.

## Commit 2: `1b48476` Installable library, no sys.path hacks

| File | Change |
|---|---|
| `pyproject.toml` | New. Package name `lbm-postprocessing`, Python >= 3.10, dependencies `numpy>=2.0`, pandas, polars, scipy, matplotlib, pyvista. Optional `dev` extra adds pytest. Packages: `data_loaders`, `physics_core`, `plotting_core`. pytest looks in `tests/` |
| `requirements.txt` | New. Same list as `pyproject.toml`, for people who prefer `pip install -r` |
| `data_loaders/__init__.py`, `physics_core/__init__.py`, `plotting_core/__init__.py` | New, empty. They make the folders proper Python packages |
| All scripts, `plotting_core/density_plots.py`, `plotting_core/particle_3d_plots.py` | Removed the `sys.path.append(...)` line |
| `README.md` | Added setup steps, a folder table and how to run |

**Why.** `sys.path.append("..")` only works when the current folder is `scripts/`. With `pip install -e .` the three packages are importable from anywhere, so a script runs from any folder, and from an IDE. The `-e` (editable) flag means library edits take effect straight away.

**Dependency note.** numpy is pinned to `>=2.0` because `np.trapezoid` does not exist in numpy 1.x.

**Checked.** `pytest` imports all three packages through the editable install (commit 6).

## Commit 3: `575d2e8` Archive retired code

Files were moved with `git mv`, so history follows them.

| From | To | Why |
|---|---|---|
| `scripts/test_arbitrary_sigmav.py`, `scripts/test_sigmav_sensitivity.py` | `archive/scripts/` | σv sensitivity tests finished (your decision) |
| `plotting_core/experiment_plots.py` | `archive/lib/` | Only used by those two tests |
| `scripts/plot_xy_heatmap.py`, `scripts/plot_xy_vectorfield.py` | `archive/scripts/` | One-off Takamatsu check for a senior's ML comparison |
| `plotting_core/utils.py` (`apply_axis_zoom`) | `archive/lib/` | Only used by the two Takamatsu scripts |
| `plotting_core/theme.py` | `archive/lib/` | Never used |
| `lbm_parsers.build_sensor_density_volume` and `density_plots.plot_sensor_3d_isosurfaces` | `archive/lib/sensor_density_volume.py` (new file, 175 lines, a copy of both functions) and removed from the live modules | Read the C++ `sensor_*_xy_number_density` planes. Replaced in August by binning `target_trajectories.csv` |
| `archive/README.md` | New | Table of what each archived file was and why it was retired |

**Why.** Archived code stays in the folder and in git, but is no longer maintained or tested. The archive README says imports may need fixing before reuse. Removing the dead functions from the live modules makes it clear which library code is in use.

**Not archived.** `physics_core/calc_footprint_FFP.py` (unused, fails on import), `footprint_plots.plot_footprint_overlay`, `turbulence.calc_tke` and `normalize_data` were listed in the review but were left in place. They belong to footprint code (on hold) or are small. Also `particle_io.load_source_trajectories` and `load_exact_particle_trajectories` (older raw-`.bin` readers) were not removed.

**Checked.** A grep for `build_sensor_density_volume`, `plot_sensor_3d_isosurfaces`, `apply_axis_zoom` and `experiment_plots` outside `archive/` finds nothing.

## Commit 4: `c6a3cfc` Particle velocity units and raw .bin reader

This is the commit that changes numbers. The reasoning is in the next section ("Particle velocity units"). The file changes:

| File | Change |
|---|---|
| `data_loaders/particle_bin.py` | New. Reader for the raw `.bin` files: `read_bin`, `find_ranks`, `load_step`, `particle_velocities`, `source_id`, `release_number` |
| `data_loaders/particle_io.py:load_trajectories_with_velocities` | Scales only `u, v, w` by `c_ref`. Adds `u_res, v_res, w_res`. `c_ref` and `flg_particle` are now arguments (defaults 100.0 and 1). Fixes `pl.col("Sz")` to `"SZ"` in the `target_coords` filter |
| `plotting_core/particle_3d_plots.py:plot_particles_with_velocity` | `u, v, w` options now show the resolved velocity (`u_res` etc.). `w_total` and `vel_mag` use the loader's `u, v, w`, which already contain SGS |
| `scripts/analyze_particle_statistics.py` | Uses `load_step` and `particle_velocities`. Everything in m/s. `sigma_v_eff = np.std(v_total)` |
| `scripts/calculate_plume_dispersion.py` | Uses `load_step` and `source_id`. Reads all rank files, not only rank 0. Figures saved relative to the repo root |
| `utils/binary_debugger.py` | Deleted, replaced by `tools/inspect_bin.py` |
| `tools/inspect_bin.py` | New. Prints rank files found, particle counts, the first rows of each field, the sources and release-number range. Checks every size header |

**Why.** See next section. Also, `calculate_plume_dispersion` read only `index0-*.bin` and `position0-*.bin`, so a run with more than one rank group would silently lose particles. `load_step` finds all `<field><rank>-<step>.bin` files and concatenates them, and `read_bin` raises `ValueError` if a file's size header does not match its content.

**`inspect_bin.py` versus the old debugger.** The old one read only rank 0, assumed shapes and printed warnings. It also used `indices` after a missing-file branch, so it would have crashed when `index0-*.bin` was absent. The new tool handles missing fields (prints "not written for this step") and takes the folder and step as arguments instead of a hard-coded path.

**Checked.** Tests `test_velocities_in_m_per_s_without_double_count`, `test_trajectory_velocities_scaled_once`, `test_header_mismatch_detected`, `test_load_step_concatenates_ranks`. The solver source was read to confirm the units (next section).

**Not re-run on real data.** `analyze_particle_statistics` and `calculate_plume_dispersion` were not run against your TSUBAME/lab data (not available in the build environment). Their numbers will change when you rerun them.

## Particle velocity units

The most important fix of the branch. All of this is read from the solver source in LBM-city, not guessed.

### What the solver writes

Function `output_particle_binary_scatter_all_LSM` in `src/Paraview_Particle.cu`, written by `fileLib::write_file` in `src/fileLib.h`.

| File | Content | Units |
|---|---|---|
| `index<r>-<n>.bin` | particle ID (int32) | none |
| `position<r>-<n>.bin` | x, y, z (float32) | m |
| `uvw<r>-<n>.bin` | u, v, w (float32) | **lattice units**, not multiplied by `c_ref` |
| `uvw_sgs<r>-<n>.bin` | SGS u, v, w (float32), only with `flg_particle = 1` | **m/s**, multiplied by `c_ref` in `copy_particle_uvw_sgs` |
| `velocity<r>-<n>.bin` | speed (float32) | **m/s**, `vel_p * c_ref_` |

Every file starts with one `uint32` word: the payload size in bytes (`write_file` writes `size = nn*sizeof(T)` and then the data). That is why the old scripts did `np.fromfile(...)[1:]`: it skips this one 4-byte word. `read_bin` now uses the word as a check instead of just dropping it.

### uvw already includes SGS

In `output_particle_binary_scatter_all_LSM`, per particle:

```cpp
u_tmp = Interpolate_Particle_Velocity(u, x, y, z, ...);   // resolved, lattice units
if (user_flags::flg_particle == 1) {
    uvw[id*3] = u_tmp + u_sgs;      // resolved + SGS
} else {
    uvw[id*3] = u_tmp;              // resolved only
}
```

So with `flg_particle = 1` (what the runs use), `uvw*.bin` is already the velocity the particle moves with. SGS must not be added again. With `flg_particle = 2` there is no `uvw_sgs` file and `uvw` is resolved only. `particle_velocities(data, c_ref, flg_particle)` handles both cases.

### c_ref

`c_ref = velocity / cfl`, from the run argument `-velocity_lbm <velocity> <cfl>` (`src/option_parser-user-def.h`, used in `src/paramDomain.cu`: `c_ref = vel_cfl_ref / cfl_ref`). The run script uses `-velocity_lbm 2.0 0.02`, so `c_ref = 2.0 / 0.02 = 100`. It is an argument now, not a hard-coded constant inside a function. If dx or dt differ in another run, check `mpirun.sh` for that run.

### The old code and the new code

All in m/s after the fix. `T` = total (what the particle moves with), `R` = resolved, `S` = SGS.

| Where | Old | New |
|---|---|---|
| `load_trajectories_with_velocities`, SGS columns | `u_sgs = u_sgs_file * c_ref` (100x too large, the file is already m/s) | `u_sgs = u_sgs_file` (not scaled) |
| same, total columns | `u = u_file * c_ref` (correct) | same |
| same, resolved | not available | `u_res = u - u_sgs` (when `flg_particle == 1`) |
| `plot_particles_with_velocity`, `w_total` | `w + w_sgs` = T + 100 S, SGS counted twice and scaled wrongly | `w_total = w` (the loader's `w` is already T) |
| same, `vel_mag` | `sqrt(u^2+v^2+w^2)` with `u` = T (right by accident); the commented-out lines suggested adding SGS | `sqrt(u_total^2 + v_total^2 + w_total^2)` |
| same, `u`, `v`, `w` options | showed T under the name "resolved" | show `u_res`, `v_res`, `w_res` |
| same, SGS TKE colouring | `0.5*(u_sgs^2+...)` with `u_sgs` 100x too large, so 10^4 x too large | same formula, now fed correct m/s, correct values |
| `analyze_particle_statistics`, `v_gs` | `uvw` raw: lattice units, and already T | `vel["resolved"][:,1]` = (`uvw * c_ref`) - SGS, in m/s |
| same, `sigma_v_eff` | `sqrt(std(v_gs)^2 + std(v_sgs)^2)`: lattice-unit T variance + m/s S variance, SGS in twice | `std(v_total)`, T in m/s |

Formulas, written out:

```
old  sigma_v_eff = sqrt( std(uvw_v)^2 + std(sgs_v)^2 )      # lattice units + m/s, SGS counted twice
new  sigma_v_eff = std( uvw_v * c_ref )                       # one array, m/s, already R + S
new  sigma_v_res = std( uvw_v * c_ref - sgs_v )               # resolved only
new  sigma_v_sgs = std( sgs_v )

old  w_total = w*c_ref + w_sgs*c_ref                          # w already contains SGS
new  w_total = w*c_ref                                        # = resolved + SGS
```

Strictly, `std(T)` is not the sum of the two variances either, because resolved and SGS parts need not be uncorrelated. Using the std of the actual total avoids needing that assumption.

### Consequences

- Any earlier figure using `u_sgs`, `w_total` or the SGS TKE colouring from `load_trajectories_with_velocities` was wrong by large factors (100x and 10^4x).
- Earlier `σv_eff` values from `analyze_particle_statistics` mixed lattice units and m/s. Treat them as invalid and rerun.
- The repo review noted the double count but not the 100x scaling of the SGS columns; that was found while reading the solver source.

### Checks

Test fixture `tests/conftest.py` builds `.bin` files with the solver's layout (size word, two rank groups, `c_ref = 100`, `uvw = (resolved + SGS)/100`). `test_velocities_in_m_per_s_without_double_count` recovers SGS `[0.1, 0.2, 0.3]`, resolved `[2.0, 0.0, 0.0]` and total `[2.1, 0.2, 0.3]`. `test_trajectory_velocities_scaled_once` does the same for the 11-column trajectory CSV (u 0.021 lattice gives 2.1 m/s, `u_sgs` 0.1 stays 0.1, `u_res` 2.0).

**C++ pass-through, checked.** The C++ suite writes `target_trajectories.csv` (11 columns `step,id,x,y,z,u,v,w,u_sgs,v_sgs,w_sgs`). In `Particle_PostProcessing_CPP/src/calculation.cpp` it reads `uvw*.bin` and `uvw_sgs*.bin` as floats and hands them to `stream_trajectories(...)` with no `c_ref` multiplication. So the CSV has the same units as the `.bin` files: `u, v, w` in lattice units (incl. SGS), `u_sgs, v_sgs, w_sgs` in m/s. `sensor_density.cpp:stream_trajectories` writes the values as received.

## Particle ID encoding

ID = `source x 10000 + release number`.

- Source IDs in `particle_position.txt` are 10001, 20001, 30001, ... and the counter adds 1 per release.
- So 54561234 is source 5456, release 1234.
- `data_loaders/particle_bin.py:source_id(ids)` is `ids // 10000`. `release_number(ids)` is `ids % 10000`. `ID_BASE = 10000`.
- Tested in `test_id_decoding` (`[10001, 10600, 20001, 54561234]` gives sources `[1, 1, 2, 5456]` and releases `[1, 600, 1, 1234]`).

**C++ suite caveat (not changed here).** In `Particle_PostProcessing_CPP`, `blending_footprint.cpp` and `residence.cpp` split IDs with `10^ID_DIGIT`. The TSUBAME config (`config/config_tsubame.py`) sets `ID_DIGIT = 3`, which would split by 1000, not 10000. For this encoding `ID_DIGIT` would need to be 4. The review found that only those two modules (blending and residence) use `ID_DIGIT`; the others decode with `/10000`. Blending height and residence are not in use (blending was a dead end), so this does not affect current results.

## Commit 5: `20493e6` XZ wind loader and virtual tower

| File | Change |
|---|---|
| `data_loaders/lbm_parsers.py:xz_yav_path` | New. Builds the solver file name `xz_yav_<var><step:08d>_<rank:04d>.csv`, e.g. `xz_yav_um00180000_0000.csv` |
| `data_loaders/lbm_parsers.py:load_xz_yav` | New. Loads several variables of one step into `{var: 2D array [z_idx, x_idx]}`. Default variables `um, vm, vv, wm, uw`. Raises `FileNotFoundError` naming the missing file |
| `physics_core/turbulence.py:virtual_tower` | New. Profile at streamwise position `x` from those fields: `z`, every field as a column, plus `sigma_v` (needs `vv`, `vm`) and `u_star` (needs `uw`, `um`, `wm`). `x` beyond the domain clamps to the last column |
| `scripts/analyze_inflow_statistics.py` | Uses `load_xz_yav` and `virtual_tower`. `t_step` is now the integer 180000 (before: the string `"00180000"`). The title shows `T=180000`; before it showed `t_step[2:6]` of the string. Figures saved relative to the repo root |
| `scripts/plot_lateral_variance_scatter.py` | Same change, loading only `vm` and `vv` |

**Why.** The same "find column x_idx, take `um[:, x_idx]`, compute σv and u*" block was copied in 5 scripts. Now the two scripts that use it share one tested function. The review counted 5 copies; the other copies are in scripts outside this commit, for example `compare_kljun_lbm.py`, which still has its own inline version (footprint code, on hold), and were left. Hard-coded `_000{rank_x}` in file names would also break for rank 10 or more; `xz_yav_path` pads to 4 digits properly.

**Same numbers.** The commit message says the output is unchanged. The functions call the same `calc_sigma_v` and `calc_u_star` as before and use `min(int(x / dx), nx - 1)` as before. The plot title text changed as noted above.

**Not checked.** Not run on real wind CSVs. The tests (`test_virtual_tower`) cover the maths on a synthetic field.

## Commit 6: `2b7e95b` pytest checks

17 tests, all on tiny files written in the solver's and the C++ suite's formats. `tests/conftest.py` has the helper `write_solver_bin` (size word plus data, as `fileLib::write_file`) and the `bin_dir` fixture.

| File | Tests | What they check |
|---|---|---|
| `tests/test_particle_bin.py` | 6 | `find_ranks`; `load_step` concatenates rank groups; missing step raises `FileNotFoundError`; a wrong size header raises `ValueError`; velocities come out in m/s with no double count; ID decoding |
| `tests/test_particle_io.py` | 6 | hit list from the time-capsule file (by sensor id and by coordinates); streamed trajectory CSV; trajectory velocities scaled once; trajectory filter by coordinates (covers the `SZ` fix); source positions and footprint counts; map file loader |
| `tests/test_wind.py` | 5 | XZ parser drops the trailing-comma column; XZ file name; virtual tower (σv 0.2, u* 0.1, clamping); σv never negative; stacked XY parser |

Also in this commit: `data_loaders/particle_io.py:load_streamed_trajectories` now passes `target_ids.to_list()` to `is_in(...)`. This silences a polars deprecation warning and does not change results.

**Not covered.** The footprint pipeline and the physics models (Kljun, Schmid). The review proposed a test that the 80 % area never exceeds the domain; it was not added because the footprint code is on hold, and it would fail until the `dx=8` bug is fixed.

**Run it.**

```sh
pip install -e .[dev]
pytest
```

Run on the branch while writing this file: `17 passed in 20.90s` (`python3 -m pytest -q`).

## Commit 7: `37411b4` Remove leftover sys.path comments

| File | Change |
|---|---|
| `scripts/plot_blending_height.py`, `scripts/plot_vertical_detection.py`, `scripts/visualize_domain.py` | Deleted one remaining `# Ensure Python can find the modular packages` comment each |

**Why.** Commit 2 removed the `sys.path` lines but left some comments pointing at them. Cosmetic only.

## Commit 8: `87262d1` Shared PyVista helpers

| File | Change |
|---|---|
| `plotting_core/pyvista_helpers.py` | New, 107 lines. See "New library pieces" below |
| `plotting_core/particle_3d_plots.py` | 772 to 485 lines. Uses the helpers; new internal `_bin_trajectories`; the second (duplicate) definition of `plot_trajectories_with_sensor` removed |
| `plotting_core/density_plots.py` | 231 to 192 lines. New internal `_load_buildings_and_volume` and `_add_pbr_buildings`; uses `add_snapshot_key` and `show_iso_grid` |

Two behaviour fixes:

| Where | Old | New |
|---|---|---|
| `particle_3d_plots.py:plot_density_cloud_with_sensor` | `density_mode` (`"pdf"` or `"concentration"`) was computed from the raw counts and then overwritten by the Gaussian-smoothed raw counts. So the mode only changed the label | The mode is applied to the smoothed field. Colour mapping looks the same; the colour-bar numbers are now in the stated units (m^-3 for pdf, pts/m^3 for concentration) |
| `density_plots.py:plot_3d_dvr` | `log_max = log10(400000 + 1)`, ignoring the `max_visible_density` argument | `log_max = log10(max_visible_density + 1)`. `scripts/plot_density_dvr.py` passes 400000, so its output is unchanged |

**Why.** The screenshot-key block was copied 7 times, the sensor box 4 times, plus voxel buildings, ground plane and the iso camera. Fixing a look or a bug in one copy left the others behind, which is how the duplicated function and the ignored `density_mode` went unnoticed.

**How it was checked, and the limit.** The commit message says every PyVista call was recorded on synthetic data before and after, and the two lists were identical except for the two fixes above. That is a stub that records calls, not a real render. The build environment has no display, so no 3D window was opened. See Open items.

## New library pieces

| Module | What it does | Used by |
|---|---|---|
| `data_loaders/particle_bin.py` | Reads raw solver `.bin` files across all rank groups, checks the size header, converts velocities to m/s (`particle_velocities`), decodes particle IDs (`source_id`, `release_number`). `FIELDS` lists the five files with dtype and values per particle | `scripts/analyze_particle_statistics.py`, `scripts/calculate_plume_dispersion.py`, `tools/inspect_bin.py`, tests |
| `data_loaders/lbm_parsers.py:xz_yav_path`, `load_xz_yav` | Solver file name for the y-averaged XZ planes, and loading several variables at once | `scripts/analyze_inflow_statistics.py`, `scripts/plot_lateral_variance_scatter.py`, `virtual_tower` input, tests |
| `physics_core/turbulence.py:virtual_tower` | Vertical profile at x from the XZ fields, with σv and u* when the inputs exist | same two scripts, tests |
| `plotting_core/pyvista_helpers.py` | `add_snapshot_key` (key `s` saves numbered screenshots `name_01.png`, ...), `show_iso_grid` (iso camera and metre grid), `add_sensor_box` (magenta box plus red wireframe), `add_voxel_buildings` (light grey with dark grey edges, optional clip at `x_start`), `add_ground_plane` (dark green plane, optional crop) | `particle_3d_plots.py` (all four plot functions), `density_plots.py` (`add_snapshot_key`, `show_iso_grid`), so the scripts `plot_sensor_density_cloud`, `plot_sensor_density_isosurfaces`, `plot_particle_trajectory`, `plot_velocity_particles`, `plot_density_dvr`, `plot_density_isosurfaces` |

Callers pass their own colours, opacities and line widths, so each scene renders as before.

## Tests

- Folder: `tests/` (`conftest.py` plus three test files, 17 tests). Details in the commit 6 table.
- They use made-up files in a temporary folder, so they need no TSUBAME or lab data and finish in seconds. (The run here took about 21 s, mostly importing pandas, polars, scipy and pyvista.)
- Run: `pip install -e .[dev]`, then `pytest` from the repo root. Result on the branch: **17 passed**.
- Purpose: if you change a loader or a unit conversion later, a failing test tells you immediately. The unit test for particle velocities is the one that would have caught the bug in the last section.

## Open items

| Item | State |
|---|---|
| `plot_lbm_contours.py`: after refining to a 1 m grid it still passes `dx = dy = 8` to smoothing, thresholds and area | **Open, on hold.** `Area_80_m2` is 64x too large (the committed CSV has 336,128 m² at z = 5 m; the whole domain is 262,144 m²), peak density 64x too small, smoothing width off by 8. `plot_footprint_metrics` inherits it |
| `schmid_params.json` renamed to `default_flat_params.json` | **Open, on hold.** 5 scripts plus `extract_variance` still read the old name and stop at start |
| `plot_spanwise_footprints.py` calls `plot_lbm_comparison(X=, Y=, ...)` | **Open.** The function now takes `X1/Y1/X2/Y2`; TypeError |
| `compare_kljun_lbm.py`: footprint from the cube case, wind from `flat_shortroughness_4mvel` | **Open, on hold.** Probably a mismatch (inferred). Please confirm |
| `plot_ensemble_ttd.py` uses the flat_3072 wind profile for the cube case | **Open.** Same question |
| `schmid_model.py` uses κ = 0.35, everything else 0.40 | **Open.** May be intended |
| Footprint pipeline (copied in 6 scripts, two smoothing formulas), `analyze_effective_velocity` own Schmid copy | **Open, on hold** (part of option C) |
| Case registry (YAML) | **Not implemented.** Design only |
| Scripts still hard-code Windows paths (`Y:\...`, `Z:\...`) and settings at the top of `main()` | **Open until the registry exists** |
| Figures: 73 MB in git (372 files) | **Open.** Plan: `figures_root` in a cloud-synced folder; existing figures stay in git for now. Scripts still write to `figures/` in the repo (now found relative to the repo root where changed) |
| C++ `ID_DIGIT = 3` versus IDs `source x 10000 + n` in blending and residence | **Open**, harmless while blending and residence stay unused |
| C++ `sensor_density.cpp:102` `harvest_ids` stops after the first hit per source | **Open**, inferred from reading the code, please confirm it is intended |
| PyVista changes (commit 8) | **Please verify by eye.** Checked with a recorded-call stub, not a real window, because the build environment has no display. Open one 3D plot (for example `python scripts/plot_density_dvr.py` or `plot_velocity_particles.py`), check buildings, sensor box, colour bar and the `s` screenshot key |
| `analyze_particle_statistics`, `calculate_plume_dispersion`, the two wind scripts | Changed but not run on real data here. Run once and compare to old figures (the particle-velocity numbers are expected to change) |
| Remaining `sys.path` hacks | None left in `scripts/`, `data_loaders/`, `physics_core/`, `plotting_core/`; the archived scripts also lost theirs |

## How to use it on your PC

1. Check out the branch and install:

   ```sh
   cd lbm-data-postprocessing
   git checkout cleanup/structure
   python -m venv .venv            # or reuse your conda env
   .venv\Scripts\activate
   pip install -e .[dev]
   ```

2. Run the checks:

   ```sh
   pytest
   ```

3. Look inside a particle output folder (all rank groups, sizes checked):

   ```sh
   python tools/inspect_bin.py <particle folder> <step>
   python tools/inspect_bin.py Y:/LBM-city/20260929_particle_flat_512x128 1600
   ```

   Check that `uvw` values times `c_ref` look like a plausible wind speed (a few m/s), and that `uvw_sgs` is much smaller.

4. Run any script from any folder, for example `python scripts/analyze_particle_statistics.py`. Paths and settings are still constants at the top of `main()`.

Drive letters used in the scripts:

| Letter | Mount |
|---|---|
| `Y:` | TSUBAME, LBM-city results |
| `X:` | lab server |
| `Z:` | old repo 1 runs |

Set `c_ref` in `analyze_particle_statistics.py` (and `load_trajectories_with_velocities` calls) from the `-velocity_lbm` line in that run's `mpirun.sh`. For the current run, 2.0 / 0.02 = 100.
