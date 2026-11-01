# CBL scales, scaled profiles and x-station profiles (2026-11-01)

**Commits**: `7bc165d`, `7d661fe`, `c59274f` (range `a6b185a..c59274f`, branch `analysis/scalar2-outputs`)

**Goal**: Mikael (kaka) asked on 2026-10-30 for a plan with three items: (1) profiles at more points across the domain and over more time steps, (2) script updates for the Deardorff velocity, (3) particle validation in convection (Stull, Practical Meteorology, ch. 19). The plan is in `planning/cbl_scales_and_particle_validation_plan_2026-10-30.md` (project files, not in the repo). He chose:
- **1a**: profiles at several x positions, taken from the planes. He noted the flat domain may show little difference between stations. That is the point: the spread between stations measures the sampling noise of one 200 s window in the 256 m wide domain and gives an error bar.
- **2, both parts**: z_i, w* and t* per window (to see the boundary layer develop), and a comparison with standard CBL curves as validation.
- The station averaging width of +-64 m was approved by kaka.

These commits cover items 1, 2a and 2b only. **Item 3 (particle validation, Prairie Grass) is not in this range.**

**Result**: All three scripts ran in the cloud container on copies of the 512 runs (`20261011_scalar2` convective, `20261017_neutral`). Only `prof` and `xz_yav` um..ww were staged; no `xz_yav_uw` and no yz files. So the <u'w'> station panel was empty and the yz vs xz_yav check did not run. `pytest`: 96 passed, 2 failed. Both failures were there before and are unrelated: `test_particle_io` (polars version) and `test_urban_morphology` (module `affine` not installed in the cloud container). **Not run** on the long run (`flat2048_long`) or on the lab PC.

Findings on the 512 convective run (200-1400 s):
- z_i grows from 307 to 373 m; w* from 1.03 to 1.12 m/s; t* is about 300-333 s.
- z_i follows the A = 0.2 jump-model curve from about 800 s.
- In the first window the rank band reaches up to about 560 m (spin-up).
- <w'w'>/w*^2 of the late windows is close to the Lenschow curve, and the heat flux is close to linear.
- Station spread of sigma_w is up to about 0.07 m/s near z_i in the last window.

## Commit 7bc165d: CBL scales per profile, reference CBL curves, profile grid options

| File | Change | Why |
|---|---|---|
| [physics_core/moments.py](../physics_core/moments.py) | `plane_moments` also returns `cov_uw` when `uw`, `um`, `wm` are given. | The <u'w'> station panel needs the covariance from the plane fields. |
| [physics_core/moments.py](../physics_core/moments.py) | New `zi_theta_gradient(moments, zmin=10, zmax=inf)`: height of the largest dtheta/dz between `zmin` and `zmax`. | Second z_i definition as a robustness check. The heat-flux minimum is a small difference of noisy moments; the theta gradient is smoother. `zmin` skips the surface layer. |
| [physics_core/moments.py](../physics_core/moments.py) | New `cbl_scales(moments, theta0=300, g=9.81)` returning `zi_flux`, `zi_grad`, `surface_flux`, `wstar`, `tstar`. `zi_grad` is searched below `2 * zi_flux`. All but `surface_flux` are NaN without a positive surface flux (neutral runs). | One call gives all scales of a window. The limit of 2 z_i is there because without it the gradient search picked 2038 m (the sponge layer) in one window of the 512 run. |
| [physics_core/cbl_reference.py](../physics_core/cbl_reference.py) | New file. `sigma_w2_lenschow(zeta)` = 1.8 zeta^(2/3) (1 - 0.8 zeta)^2; `heat_flux_linear(zeta, A=0.2)` = 1 - (1 + A) zeta; `zi_encroachment(t, zi0, flux, gamma, A)`: z_i^2 = zi0^2 + 2 (1 + 2A) flux t / gamma. NaN outside 0 <= zeta <= 1 for the first two. | Reference curves for the validation. Citations: Lenschow, Wyngaard & Pennell 1980 (J. Atmos. Sci. 37, 1313-1326); Stull 1988; Tennekes 1973. The citations were checked online; **the formulas were not checked in the papers and are marked [U]**. |
| [plotting_core/profile_plots.py](../plotting_core/profile_plots.py) | `plot_profile_grid` gets `ylabel="z [m]"` and `references={column: (x, z, label)}` (black dashed curve in that column's panel). The legend now collects lines from every panel. | Normalised plots need "z / z_i" on the axis and the reference curves. The legend change is needed because a reference may sit in a panel other than the first. Defaults keep old callers unchanged. |
| [tests/test_lbm_output.py](../tests/test_lbm_output.py) | New `test_plane_moments_cov_uw`, `test_zi_theta_gradient_and_cbl_scales`, `test_cbl_reference_curves`. | Cover the three additions. |

## Commit 7d661fe: profiles at x stations and their spread per window

| File | Change | Why |
|---|---|---|
| [scripts/plot_profiles_by_station.py](../scripts/plot_profiles_by_station.py) | New. U, sigma_u, sigma_v, sigma_w and <u'w'> from `xz_yav` averaged over +-`HALF_WIDTH` (64 m) around each station, next to the domain mean from `prof`. Writes `station_profiles_step*.png`, `station_spread.png` (std over stations per window) and `station_profiles.csv` to `<figures>/<set>/station_profiles/<run label>/`. | Item 1a: the station-to-station spread is the error bar of one 200 s window. |
| same | Stations default to the yz-plane positions (`iout` in `header.txt`); `STATIONS_M` overrides them. | A yz vs xz_yav cross-check is then possible: the script prints the largest difference between the y-average of each yz plane and the xz_yav column at the same x (both files have 6 decimals, so about 1e-6 expected). |
| same | Raw moments are averaged over the band first, then central moments are formed. | One station = one sampling region, so the variance includes the differences inside the band. |
| same | The <u'w'> panel stays empty when the run has no `xz_yav_uw` files. | Those files are not in every run. |

The script's docstring gives what the figure measures, why, the reference (horizontal homogeneity; there is no published value for the spread) and the units, as the CLAUDE.md rule asks ([2026-10-21_explain-statistics-rule.md](2026-10-21_explain-statistics-rule.md)).

## Commit c59274f: CBL scales per window and mixed-layer scaled profiles

| File | Change | Why |
|---|---|---|
| [scripts/plot_cbl_scales.py](../scripts/plot_cbl_scales.py) | New. z_i (flux minimum and theta gradient), w*, t* per 200 s window for the domain and for each rank segment, with the jump-model z_i growth drawn for A = 0 and A = 0.2, plus theta and heat-flux profiles. Writes `cbl_scales_vs_time.png`, `theta_flux_profiles_<case>.png` and `cbl_scales.csv`. | Item 2a: see how the boundary layer develops and when particle statistics can be scaled by z_i and w*. |
| same | Settings copy the run's initial state from LBM-city `src/Define_user.h`: `ZI0 = 300` (neutral layer to 300 m), `GAMMA = 0.01` K/m above, `FLUX_IN = 0.1` K m/s. | Inputs of the jump model. They must be changed for runs with another initial state. Copied by hand, not read from the run. |
| same | z_i and w* are resolved in x only per rank segment (4 x 1024 m on the long run). | The heat flux exists only in the per-rank `prof*.csv`, not in the planes. |
| same | Total heat flux = resolved <w'theta'> + model SGS flux; theta0 = `out_ref` of `header.txt`. | Taken as in `convective_scales`; w* = (g/theta0 flux z_i)^(1/3), t* = z_i/w* (Deardorff 1970; Stull 1988 Sec. 4.2, checked by kaka). |
| [scripts/plot_cbl_normalised_profiles.py](../scripts/plot_cbl_normalised_profiles.py) | New. Variances / w*^2, heat flux / surface flux and S_w against z/z_i, with the Lenschow and linear-flux curves. One figure per window and one per run with all windows (`cbl_normalised_step*.png`, `cbl_normalised_all_windows_<case>.png`, `cbl_normalised_profiles.csv`). Runs without positive surface flux (neutral) are skipped. | Item 2b: validation against standard CBL curves. |
| same | S_w is hidden where <w'w'>/w*^2 < `MIN_VAR_W = 0.01`. | Above the CBL S_w reached about 20 (ratio of two near-zero moments). |
| same | No curve for <u'u'>, <v'v'> (roughly 0.3 w*^2 in the mixed layer) or for w skewness. | No reference found yet; marked [U]. |
| [run_sets.yaml](../run_sets.yaml) | New set `flat2048_long`: `convective_long: flat_2048x128x704/20261030_scalar2`. Description: 4096 x 256 x 1408 m, 2400 s, sources x 8-248 m, dist seed 12345, SGS fix. | Kaka's new long run. It expects `<lbm_results>/flat_2048x128x704/20261030_scalar2/output`. His data is now in `Z:/LBM-city/20261030_output_flat_2048x128x704_scalar2`, so it has to be copied or linked into that layout. |
| [README.md](../README.md) | Three command lines for the new scripts and a short note on the plan and the `Define_user.h` settings. | So the scripts can be found. |

## Physics and numerics notes

- z_i definition: the standard one is the heat-flux minimum (`zi_flux`). `zi_grad` (largest dtheta/dz, searched below `2 * zi_flux`) is only a check. Without the 2 z_i limit it can jump into the sponge layer.
- Jump-model z_i assumes constant surface flux from t = 0 and a neutral layer up to `ZI0`. On the 512 convective run the data follow it from about 800 s; earlier windows include spin-up.
- Nothing in the solver or in existing scripts changed. `plot_profile_grid` only gained optional arguments.

## What was deliberately left alone

- Item 3 (particle validation in convection, Prairie Grass, Stull ch. 19) is not started.
- The [U] formulas are not checked in the papers (Lenschow 1980, Stull 1988, jump model). Do not present results with these curves before checking.
- No reference curve for <u'u'>, <v'v'> and w skewness.
- `flat2048_long` was not run; the data layout still has to be prepared.

## How to check

```sh
pytest
python scripts/plot_profiles_by_station.py --set flat2048_long
python scripts/plot_cbl_scales.py --set flat2048_long
python scripts/plot_cbl_normalised_profiles.py --set flat2048_long
git log --oneline a6b185a..c59274f
git diff --stat a6b185a c59274f
```

On the long run, check first that the yz check line printed by the station script is about 1e-6, that the <u'w'> panel is filled (needs `xz_yav_uw` and yz files), and that `zi_grad` stays near `zi_flux`.
