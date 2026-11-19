# Plume height compared with matching references (2026-11-17)

**Commits**: `6cb5226` (range `29d68aa..6cb5226`, branch `analysis/scalar2-outputs`)

**Goal**: The figures `dispersion_vertical_<run>.png` and `dispersion_distance_<run>.png` (see [2026-11-01_particle-dispersion-validation.md](2026-11-01_particle-dispersion-validation.md)) compared the model's MEAN particle height with Stull's eq. 19.32. Stull's formula is the height of the concentration MAXIMUM (the plume centreline), so this was not a like-for-like comparison. Mikael pointed this out. Approved plan (2026-11-17): the left panel shows the model's height of maximum concentration against Stull; the right panel shows the model mean height and sigma_z against Willis & Deardorff (1976) Fig. 2, which is the mean particle height (their eq. 8).

**Result**: `tests/test_cbl_dispersion.py` (3 tests) passes in the cloud. The figure layout was checked with synthetic data only. **Not yet run on real data** (needs `reduced.npz` on Mikael's lab PC).

## Commit 6cb5226: model max vs Stull, model mean vs W&D 1976 Fig. 2

| File | Change | Why |
|---|---|---|
| [validation_data/willis_deardorff_1976/fig2_mean_height.csv](../validation_data/willis_deardorff_1976/fig2_mean_height.csv) | New. Mikael digitised W&D 1976 Fig. 2 with WebPlotDigitizer. Columns `series,X,z_mean`. Series: `tank_l_zi_1.9` (18 points), `tank_l_zi_4.0` (23), `numerical_deardorff_1972` (41). Header gives the case parameters and accuracy (about +-0.01 in X and Z_p). | Reference for the mean particle height. l/z_i is the horizontal sidewall spacing over z_i (paper Table 1). |
| [data_loaders/willis_deardorff.py](../data_loaders/willis_deardorff.py) | New reader `read_wd1976_mean_height()`: `{series: DataFrame(X, z_mean)}` sorted by X; empty dict if the file is missing. | The l/z_i 1.9 export came in reverse order, so every series is sorted by X. Points slightly below X = 0 are digitising noise and were kept as digitised. |
| [physics_core/cbl_dispersion.py](../physics_core/cbl_dispersion.py) | New `peak_height_of_density(Z, density, smooth=3)`: height / z_i of the concentration maximum of each row. Rows without particles give NaN. | Stull eq. 19.32 describes the maximum, not the mean. Each row is smoothed with a running mean over 3 Z bins first, so single noisy bins do not set the maximum. |
| [scripts/plot_dispersion_validation.py](../scripts/plot_dispersion_validation.py) | `plot_vertical` (figures 1 and 2): left panel old line `profile_moments_of_density` mean (red) replaced by `peak_height_of_density` (red, "model height of max. concentration") next to the Stull curve. Right panel keeps model mean and sigma_z (now line width 2, colours C0 / C1) and adds the three W&D curves (`WD1976_STYLE`: grey triangles, circles, dashed line). New constant `PEAK_SMOOTH_BINS = 3`. Figure width `13` to `15` inches; right legend moved outside the axes (`loc="upper left", bbox_to_anchor=(1.01, 1.0)`, fontsize 7). Docstring updated. | Compare each reference with the quantity it describes. The wider figure and outside legend keep the legend off the curves. |
| [tests/test_cbl_dispersion.py](../tests/test_cbl_dispersion.py) | New, 3 tests: Gaussian maximum found within 0.011; empty row gives NaN and a uniform density gives mean 0.5 and sigma 1/sqrt(12); the W&D file has the three series, sorted, with z_mean between 0 and 0.7. | Checks for the new function and the new data file. |

Behaviour change of the figures: the red line on the left panel is now the height of the maximum, not the mean. The mean still appears on the right panel (blue). To go back, restore the old `profile_moments_of_density` line in `plot_vertical` (`git revert 6cb5226` undoes the whole commit). Nothing in the numbers of `reduced.npz` changes.

## Differences between tank and model (also in the script docstring)

- The tank releases an instantaneous line source at z_r/z_i = 0.050-0.067; the numerical model releases at 0.1 z_i. Ours is a continuous release at 0.1 m (about 0.0003 z_i).
- The tank has no shear and turns time into distance with x = U t. Ours has a sheared mean wind, so our lift-off is expected later.
- The tank results are stated valid for 0.13 < X < 3.0 (paper eq. 7).

## What was deliberately left alone

- The Stull formula, the well-mixed limits (0.5 and 0.29) and all other figures of the script are unchanged.
- No data was run; the reducer output is not touched.

## How to check

```sh
python -m pytest tests/test_cbl_dispersion.py
python scripts/plot_dispersion_validation.py --set flat2048_long   # on the lab PC, needs reduced.npz
```
