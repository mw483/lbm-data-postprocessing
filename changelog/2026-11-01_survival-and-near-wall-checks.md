# Survival, first exit, per-age z_i and near-wall checks for the particle validation (2026-11-01)

**Commits**: `fb1c21c`, `1633136` (range `986318f..1633136`, branch `analysis/scalar2-outputs`)

**Goal**: Check whether the particle figures of the long run (`flat_2048x128x704`, 20261030) are distorted by particles leaving the domain. This continues [2026-11-01_particle-dispersion-validation.md](2026-11-01_particle-dispersion-validation.md).

Request (Mikael, 2026-11-01). After seeing the dispersion figures of the long run, Mikael suspected that the mean particle height z/z_i stops rising and then drops because particles leave the domain, not because of mixing. He also noted that the particle count plateaus at 550-650k, although about 990k would be expected without losses. He approved five checks:
1. Survival against age and plume front, so that the validation stops at the first exit through the outflow.
2. Survivor normalisation of the plume concentration.
3. Fraction of particles above z_i against age.
4. A zoom of the particle density near the ground. He asked for 0-20 m; it was implemented as 0-40 m.
5. Scaling each age by the z_i of its own window.

Why these checks:
- LBM-city deletes particles at the global x and y edges (`src/boundary_flag_particle.cu` in the LBM-city repo) although the flow is periodic.
- Losses at the y edges do not bias the height statistics per age (the flow is uniform in y). They do lower a concentration that is divided by all released particles.
- Losses at the x edges remove the fastest particles first (survivor bias). Everything after the first exit is biased.
- z_i grows from about 345 to 409 m during the particle period. One period-mean z_i therefore mis-scales early and late ages by about 5-10 %.
- The contour plots showed a thin bright layer a few cells above the ground. This could be a pile-up near the wall.

**Result**: Tested in the cloud container only. **Not run on the real long-run data.**
- New unit tests pass: a survivor-weighted plume restores C_y/Q = 1/U when half the particles are lost; survival and plume front; per-age regridding keeps a well-mixed profile at 1; fraction above; per-age scales.
- Full suite: 104 passed, 2 failed. Both failures are older and unrelated: `test_particle_io` (polars version) and `test_urban_morphology` (module `affine`).
- The reducer and `plot_dispersion_validation.py` ran end to end on synthetic particle bins with the real 512 run wind output. The figures render. The synthetic bins have no particle loss.

## Commit fb1c21c: survivor-weighted plume and survival per age in the reducer

Design: the survivor weight is n_sources / alive(age), so the number of live particles per age must be known before the main pass. The reducer therefore does a first pass that reads only the index files. `--no-survivor-pass` skips it.

| File | Change | Why |
|---|---|---|
| [physics_core/particle_bin_stats.py](../physics_core/particle_bin_stats.py) | New `survivor_weights(alive_per_age, n_sources)` = n_sources / alive(age), 0 for ages without particles. | Makes `plume_concentration` give C_y/Q of the survivors, as if no particle had left. Valid while lost particles are statistically like survivors (y-edge losses; not x-edge losses). |
| same | New `survival_by_age(acc, n_sources, per_age)`: `age_count` divided by n_sources x S(age). | Share of released particles still in the domain, per age. |
| same | New `leading_edge(acc, quantile=0.99)`: per age, the x - x_source reached by 99 % of particles and by the furthest one (upper bin edges, so within one bin width). | Plume front, to find when the first particles reach the outflow. |
| same | `new_plume_acc` adds `plume_surv_hist`. `add_plume(..., key="plume_hist")` and `plume_concentration(..., key="plume_hist")` take a histogram key. | The survivor-weighted histogram sits next to the old one. Default key is unchanged, so old calls behave as before. |
| [scripts/reduce_particle_bins.py](../scripts/reduce_particle_bins.py) | First pass over the index files counts upstream particles alive per age. The main pass adds a second plume histogram with `survivor_weights`. New option `--no-survivor-pass`. Meta gets `survivor_pass`. `reduced.npz` also stores `plume_outputs_per_age` (S(age)) and `plume_alive_per_age`. | Input for the survival figure and the survivor curves. |

Cost: one extra read of all index files on TSUBAME (the log prints `survivor pass: N index outputs in X s`).
Compatibility: old `reduced.npz` files still work for every figure except the survivor curves. The plot script prints a warning.
To revert the new behaviour: run the reducer with `--no-survivor-pass`. The plume then has only `plume_hist`, as before.

## Commit 1633136: survival figure, first-exit marker, per-age z_i, near-wall figure

| File | Change | Why |
|---|---|---|
| [scripts/plot_dispersion_validation.py](../scripts/plot_dispersion_validation.py) | New `survival_<run>.png` (and `survival_<run>.csv`), three panels against X = t w*/z_i: (a) share of released particles in the domain, (b) plume front (99 % and furthest particle) with the exit distances of the most downstream source (x = `--upstream-xmax`) and of a source at x = 0, (c) share above z_i and above 1.2 z_i. | Checks 1 and 3. |
| same | `mark_exit`: the first exit through the outflow is marked (grey area, dash-dot line) on every X figure, and as a vertical line on the ground-level figure. The exit is the first age at which the furthest particle could have left from the most downstream upstream source. | Check 1: the comparison with the experiments is valid only left of this line. |
| same | Distance and ground-level figures use `plume_surv_hist` when `reduced.npz` has it (titles say "survivors" or "all released"). The ground-level figure also keeps the all-released curve and adds the survivor curve dashed. | Check 2. |
| same | New `near_wall_<run>.png`: lowest `NEAR_WALL_TOP = 40` m. Left: z_i p(z given age) at ages 20, 60, 120, 300, 600 s. Right: steady plume C_y U_ml z_i / Q at x = 100, 300, 1000, 2000 m. Log x axis, reference line at 1. | Check 4. The bins are the reducer's `--dx` (2 m), so structure finer than one cell is not visible. The left panel uses the period-mean z_i and w*, not the per-age scales. |
| same | `PER_AGE_SCALES = True`: figures 1 and 4 scale each age by its own z_i and w*. Figure 1 uses `lagrangian_cy_per_age` on a Z grid of `Z_GRID_STEP = 0.01`. `run_scales` now also returns `t_mid` (window centre). Distance-based figures (2, 3, 5) keep the period mean. | Check 5. Every distance mixes many ages, so one scale per distance is kept. Set `PER_AGE_SCALES = False` to get the old scaling. |
| [physics_core/cbl_dispersion.py](../physics_core/cbl_dispersion.py) | New `lagrangian_cy_per_age` (cumulative distribution of each age interpolated at Z x z_i(age), differenced onto one shared Z grid), `fraction_above` (linear inside the bin that holds the height), `scales_per_age`. | Helpers for checks 3 and 5. |
| same | `scales_per_age`: per-age z_i and w* = mean of z_i(t), w*(t) over the times when particles of that age are sampled (release start + age to the last output). z_i(t) is linearly interpolated between the 200 s window centres and held constant outside them. Ages that do not fit into the interval are NaN. | The sampling interval of an age is shorter for older ages, so old ages see the later, deeper layer. |
| [tests/test_particle_bin_stats.py](../tests/test_particle_bin_stats.py) | Tests for the survivor weight, survival, front, per-age regridding, fraction above, per-age scales. | Cover the additions. |
| [README.md](../README.md) | One paragraph: the two new figures, the survivor curves, the reducer rerun, `--no-survivor-pass`. | So it can be found. |

The docstring of the script gives, for figures 4 and 5, what they measure, why, the reference and the units, as `CLAUDE.md` requires.
- Survival and front (4a, 4b): no reference. They are a check of the other figures, not a validation.
- Fraction above z_i (4c): the tank and LES show that near-ground plumes reach z_i at X of about 1-2 and that little material is entrained above it. This is marked [U]; there is no single published value.
- Near wall (5): well-mixed value 1. Thomson 1987 (J. Fluid Mech. 180, doi:10.1017/S0022112087001940) is cited for the well-mixed criterion, marked [U]. No data set resolves the first cells of a CBL.

## What was deliberately left alone

- The particle code in LBM-city (deletion at the x and y edges) is not changed. The checks only show how much it matters.
- The survivor weight cannot correct x-edge losses, because those remove the fastest particles. It is a correction for y-edge losses; beyond the first exit the figures stay biased, which is why the exit is marked.
- Distance-based figures keep the period-mean z_i and w*.
- The near-wall figure uses the 2 m bins of the reducer. A finer zoom needs a rerun with a smaller `--dx`.

## Not checked

- Nothing was run on the real long-run data.
- The survivor normalisation was verified only by the unit test (half the particles lost), not on data with real losses.
- The reference statements marked [U] (fraction above z_i, Thomson 1987) were not checked in the source.

## How to check

Mikael must rerun the reducer on TSUBAME for the survivor curves (it reads the index files once more). Then, on the PC:

```sh
python scripts/reduce_particle_bins.py ...        # same arguments as for the long run; add --no-survivor-pass to skip the new pass
python scripts/plot_dispersion_validation.py --set flat2048_long
pytest tests/test_particle_bin_stats.py
git diff 986318f..1633136 --stat
```

New figures go to `<figures>/flat2048_long/dispersion_validation/`: `survival_<run>.png`, `survival_<run>.csv`, `near_wall_<run>.png`.
