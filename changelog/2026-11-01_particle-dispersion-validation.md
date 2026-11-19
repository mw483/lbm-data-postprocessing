# Particle dispersion validation in convection, explicit run folders (2026-11-01)

**Commits**: `3093e32`, `9589d36`, `a65cf38` (range `7db7325..a65cf38`, branch `analysis/scalar2-outputs`)

**Goal**: Item 3 of the approved plan `planning/cbl_scales_and_particle_validation_plan_2026-10-30.md` (project files, not in the repo): check that the Lagrangian particles behave correctly in a convective boundary layer (CBL). The earlier items 1, 2a and 2b are in [2026-11-01_cbl-scales-and-station-profiles.md](2026-11-01_cbl-scales-and-station-profiles.md); this entry continues it. The first commit is a small prerequisite: kaka (Mikael) works on his own PC over an rclone drive (Z:), and the new long run is not in the `<lbm_results>/<case>/<date>_<tag>/...` layout.

References used:
- Willis & Deardorff water-tank experiments, as summarised in Stull, Practical Meteorology, Sec. 19.7: centreline height (eq. 19.32) and the well-mixed limits (mean height 0.5 z_i, standard deviation 0.29 z_i).
- Weil et al. 2004: cited only, not compared numerically.
- Prairie Grass 1956 field data. kaka supplied the files from https://www.harmo.org/jsirwin/PrairieGrassDiscussion.html into `validation_data/prairie_grass/` (the cloud session could not download them).

**Result**: Tested in the cloud container only, on synthetic data and the real Prairie Grass files. **Not run on any real particle data** (no particle bins in the cloud) and not on the lab PC.
- `pytest`: 101 passed, 2 failed. Both failures were there before and are unrelated: `test_particle_io` (polars version) and `test_urban_morphology` (module `affine` not installed).
- New tests: a uniform wind gives C_y/Q = 1/U exactly; `outputs_per_age` with `release_every` 2; the Prairie Grass files parse; the Monin-Obukhov fit recovers u*, theta* and L of a synthetic profile; run-set mappings (in `tests/test_run_sets.py`).
- End to end, the reducer ran on synthetic bins. A uniform wind of 4 m/s gave C_y/Q alternating 0.1 / 0.15 around the expected 1/(U dz) = 0.125. This comes from the 8 m x bins against the 3.2 m release spacing; the average is correct.
- The validation script ran on synthetic particles with the real 512 convective `prof` files for the scales and the real Prairie Grass data. Particles uniform in height gave mean 0.5, sigma 0.29 and density about 1, as expected.
- Real Prairie Grass data: the 32 unstable runs fall onto one falling curve in C_y U8 z_i / Q against X, roughly following X^-1.5 between X of about 0.01 and 0.5.

## Commit 3093e32: a run can be given as explicit folders

Why: kaka's long run is in `Z:/LBM-city/20261030_output_flat_2048x128x704_scalar2` and `Z:/LBM-city/20261030_particle_flat_2048x128x704_scalar2/postprocess`. He tried to set `lbm_results` to one run's folder. That cannot work, because the scripts append `<case>/<run>/output` themselves. A decision card was posted with options; kaka chose "Explicit paths".

| File | Change | Why |
|---|---|---|
| [data_loaders/run_sets.py](../data_loaders/run_sets.py) | A run may be a mapping with keys `output`, `particle_postprocess`, `particle_reduced` (constant `RUN_FOLDER_KEYS`). Unknown keys or an empty mapping raise an error. The old string form is still accepted. | Lets one run point at any folders. |
| [data_loaders/local_paths.py](../data_loaders/local_paths.py) | `wind_dir`, `particle_postprocess_dir` and `particle_reduced_dir` return the folder from the mapping when the run is a dict (new helper `_explicit_folder`, `KeyError` if the key is missing). | Scripts keep calling the same functions. |
| [run_sets.yaml](../run_sets.yaml) | `flat2048_long`, run `convective_long`: was `flat_2048x128x704/20261030_scalar2`, now `output: Z:/LBM-city/20261030_output_flat_2048x128x704_scalar2` and `particle_postprocess: Z:/LBM-city/20261030_particle_flat_2048x128x704_scalar2/postprocess`. No `particle_reduced` yet. The header comment explains the mapping form. | Uses kaka's folders. This revises the note in the earlier entry that the data had to be copied or linked into the layout. |
| [tests/test_run_sets.py](../tests/test_run_sets.py) | Tests for the mapping form. | Cover the change. |
| [README.md](../README.md) | One sentence on the mapping form. | So it can be found. |

Old string runs behave exactly as before. To revert: put the string back in `run_sets.yaml`.

## Commit 9589d36: per-source plume histogram, Prairie Grass reader, surface-layer fit

Question kaka asked: how can an area release be compared with point-release experiments? Answer used: every particle is measured from its own source and its own release (from the particle ID), so the many sources act as an ensemble of repeated point releases. Only upstream sources are used (`--upstream-xmax`), the same as the age statistics.

| File | Change | Why |
|---|---|---|
| [physics_core/particle_bin_stats.py](../physics_core/particle_bin_stats.py) | New `new_plume_acc`, `add_plume`: one 2D histogram over (x - x_source, z). Each particle is weighted by 1 / S(age). | A point-source plume against distance, built from the area release. |
| same | New `outputs_per_age(outputs, release_start, release_every, n_age)`: S(age) = number of outputs read at which a particle of that age can occur. | The weight 1 / S makes each age count once per release, so the sum is the steady plume rather than depending on how many outputs were read. |
| same | New `plume_concentration(acc, n_sources, release_interval)`: C_y / Q = H tau / (n_sources dx dz) [s/m^2]. H is the weighted histogram, tau the release interval. | Steady crosswind-integrated concentration of one continuous point source. Complete only for distances reached within the oldest age read. |
| [scripts/reduce_particle_bins.py](../scripts/reduce_particle_bins.py) | Writes the `plume` accumulator into `reduced.npz`. New option `--plume-dx` (default 8 m, x bin); z bins use `--dx`. The list of available outputs is now built first, so S(age) is known before the loop. | Input for the new script. |
| [data_loaders/prairie_grass.py](../data_loaders/prairie_grass.py) | New. Reads arcs (ASTM D6589 format), integrates across the wind (`crosswind_integrated`), reads profiles, daytime z_i (`.xls`) and the evaporation corrections of Table 5.4 (multiplied onto the concentrations). Missing value -999. | Field data for the ground-level comparison. |
| [physics_core/surface_layer.py](../physics_core/surface_layer.py) | New. `fit_profiles` fits u*, theta*, L to wind and temperature profiles (Businger-Dyer / Paulson forms, von Karman 0.4); `surface_heat_flux(ustar, tstar)`. | Prairie Grass files contain no heat flux, u* or L. **Formulas not checked in the source [U].** |
| [physics_core/cbl_dispersion.py](../physics_core/cbl_dispersion.py) | New. `stull_centreline` (Stull eq. 19.32: Z_CL = 0.5 + 0.5/(1 + 0.5 X^2) cos(2 pi X/4 + arccos(2 zs - 1))), `lagrangian_cy` (C_y U z_i / Q = z_i times the density of z at a given age), `profile_moments_of_density`, well-mixed limits 0.5 and 1/sqrt(12). | Reference curve and the Lagrangian form of the scaled concentration. The sensitivity of eq. 19.32 to the source height is **not checked [U]**. |
| [tests/test_particle_bin_stats.py](../tests/test_particle_bin_stats.py) | Tests listed under Result. | Cover the additions. |

**Old `reduced.npz` files have no plume histogram.** The new script stops with a clear error on them. For the long run the reducer must be rerun on TSUBAME with the long-run arguments.

## Commit a65cf38: `plot_dispersion_validation.py`

| File | Change | Why |
|---|---|---|
| [scripts/plot_dispersion_validation.py](../scripts/plot_dispersion_validation.py) | New. Run set via `--set`; each run needs `particle_reduced` and `output`. Writes `dispersion_vertical_<run>.png`, `dispersion_distance_<run>.png` and `ground_level_concentration.png` to `<figures>/<set>/dispersion_validation/`. The docstring gives, for each figure, what it measures, why, the reference and the units, as `CLAUDE.md` requires. | Item 3 of the plan. |
| same | Figure 1 (vertical): height distribution against X = t w*/z_i, with the Stull centreline and the well-mixed limits. Uses the particle age histograms. Ages with fewer than `MIN_COUNT = 2000` samples are left out. | Water-tank comparison: lift-off and the approach to the well-mixed state. |
| same | Figure 2 (distance): same from the steady plume, X = x w*/(U_ml z_i), with U_ml the mean wind over 0.1-1 z_i. | Shows how much distance-based X differs from age-based X when the wind changes with height. |
| same | Figure 3 (ground level): C_y U8 z_i / Q against X = x w*/(U8 z_i), and dimensional C_y / Q [s/m^2] against x. Model value = 0-2 m layer (`GROUND_DZ_BINS = 1`, first cell). Prairie Grass samplers were at 1.5 m and the release at 0.46 m; the model releases at 0.1 m (`SOURCE_HEIGHT`). | Tests the near-ground part of the model, which figure 1 does not. |
| same | U at 8 m for both model and data in figure 3, because Prairie Grass profiles only cover 0.25-16 m. | The only height available in both. |
| same | Prairie Grass selection: L < 0, positive heat flux, daytime z_i and U8 available. Result: 32 runs, 160 arcs. Experiments 63-68 (release at 1.5 m) are excluded. u*, theta*, L and the heat flux come from the Monin-Obukhov fit over levels 0.5-8 m, z0 = 0.006 m (from the file header) [U]. w* is built from that flux and Briggs' daytime z_i. | The files lack these quantities. |
| same | Prairie Grass concentration unit mg/m^3, from the tower file; not confirmed for the arcs file [U]. | Reported as found. |
| same | Settings in the first lines: `PG_Z0`, `PG_FIT_ZMIN`, `U_REF_HEIGHT`, `SOURCE_HEIGHT`, `X_MAX = 4`, `Z_MAX = 1.5`. | Change them there. |
| [pyproject.toml](../pyproject.toml) | New optional extra `validation = ["xlrd>=2.0.1"]`. | Needed to read the `.xls` z_i file. Install with `pip install -e .[validation]`. |
| [README.md](../README.md) | Command line and a note on the requirements (new reducer output, Prairie Grass files, `[validation]` extra). | So it can be found. |

## Physics and numerics notes

- Nothing in the solver or in existing statistics changed. Existing `reduced.npz` outputs keep their old keys; the reducer only adds the `plume` entries.
- Steady plume weight: each particle counts 1 / S(age). The estimate is the plume of one continuous point source under the assumption that all sources see the same flow. The 8 m x bins against the 3.2 m release spacing make single bins alternate (see Result); average over several bins.
- Figure 3 compares a 0-2 m layer with samplers at 1.5 m and a release at 0.1 m with one at 0.46 m. Differences at short distance may come from this.

## What was deliberately left alone

- Well-mixed test (3d of the plan): skipped by kaka.
- Weil et al. 2004: cited, no numerical comparison.
- No comparison of the Prairie Grass numbers with published analyses.
- No run on the long run or any real particle data. The reducer has to be rerun first.

## Not checked

- The Monin-Obukhov profile forms and the fit [U].
- The X^-3/2 guide slope (free-convection similarity) [U].
- Stull eq. 19.32 and its sensitivity to the source height [U]; the tank source height z_s/z_i of about 0.07 is also [U].
- Prairie Grass concentration unit [U].

## How to check

```sh
pip install -e .[dev,validation]
pytest
# on TSUBAME, for the long run (use the long-run arguments; --plume-dx defaults to 8):
python scripts/reduce_particle_bins.py --help
# on the PC, after copying particle_reduced and adding it to the run in run_sets.yaml:
python scripts/plot_dispersion_validation.py --set flat2048_long
git log --oneline 7db7325..a65cf38
git diff --stat 7db7325 a65cf38
```

First checks on real data: the uniform-in-height end state should give mean about 0.5 and sigma about 0.29 at late X; the ground-level curve should fall with X close to the Prairie Grass collapse.
